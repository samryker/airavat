import os
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from enum import Enum
import json
import uuid
import base64
import io

# File processing imports
import PyPDF2
import pandas as pd
import numpy as np

# Google Cloud imports
from google.cloud import storage
from firebase_admin import firestore

# AI/ML imports
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class ReportType(Enum):
    GENETIC_TEST = "genetic_test"
    DNA_SEQUENCE = "dna_sequence"
    GENE_EXPRESSION = "gene_expression"
    VCF_FILE = "vcf_file"
    FASTQ_FILE = "fastq_file"
    FASTA_FILE = "fasta_file"
    LAB_REPORT = "lab_report"
    UNKNOWN = "unknown"

class ReportStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class GeneticMarker:
    """Represents a genetic marker found in analysis"""
    marker_id: str
    gene_name: str
    chromosome: str
    position: int
    reference_allele: str
    alternate_allele: str
    significance: str  # benign, likely_benign, uncertain, likely_pathogenic, pathogenic
    clinical_impact: str
    frequency: Optional[float] = None
    confidence_score: Optional[float] = None

@dataclass
class CRISPRTarget:
    """Represents a CRISPR editing target"""
    target_id: str
    gene_name: str
    target_sequence: str
    guide_rna: str
    efficiency_score: float
    off_target_risk: str  # low, medium, high
    therapeutic_potential: str
    clinical_notes: str

@dataclass
class GeneticReport:
    """Complete genetic analysis report"""
    report_id: str
    user_id: str
    report_type: ReportType
    upload_date: datetime
    analysis_date: Optional[datetime] = None
    status: ReportStatus = ReportStatus.PENDING
    file_path: str = ""
    file_size: int = 0
    markers: List[GeneticMarker] = None
    crispr_targets: List[CRISPRTarget] = None
    summary: Dict[str, Any] = None
    raw_data: Dict[str, Any] = None

class GeneticAnalysisService:
    """
    Comprehensive genetic analysis service for Airavat Medical AI Assistant
    Handles file upload, parsing, analysis, and CRISPR target generation
    """
    
    def __init__(self, db: firestore.client = None, storage_client: storage.Client = None):
        self.db = db
        self.bucket_name = os.getenv("FIREBASE_STORAGE_BUCKET", "airavat-a3a10.appspot.com")
        
        # Initialize storage client only if credentials are available
        try:
            self.storage_client = storage_client or storage.Client()
            self.bucket = self.storage_client.bucket(self.bucket_name)
            logger.info("Google Cloud Storage client initialized successfully")
        except Exception as e:
            logger.warning(f"Google Cloud Storage not available: {e}")
            self.storage_client = None
            self.bucket = None
        
        # Initialize Gemini for analysis
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if gemini_api_key:
            genai.configure(api_key=gemini_api_key)
            self.model = genai.GenerativeModel('gemini-1.5-pro')
        else:
            self.model = None
            logger.warning("GEMINI_API_KEY not found. Genetic analysis will be limited.")
    
    async def upload_genetic_report(self, user_id: str, file_data: bytes, 
                                  filename: str, report_type: str = "unknown") -> str:
        """
        Upload and process a genetic report file
        """
        try:
            # Generate unique report ID
            report_id = str(uuid.uuid4())
            
            # Determine report type
            detected_type = self._detect_report_type(filename, file_data)
            report_type_enum = ReportType(detected_type)
            
            # Upload to Firebase Storage if available
            file_path = f"genetic_reports/{user_id}/{report_id}/{filename}"
            if self.bucket:
                blob = self.bucket.blob(file_path)
                blob.upload_from_string(file_data, content_type=self._get_content_type(filename))
                logger.info(f"File uploaded to Firebase Storage: {file_path}")
            else:
                logger.warning("Firebase Storage not available. File will be processed in memory only.")
                file_path = "memory_only"
            
            # Create report record
            report = GeneticReport(
                report_id=report_id,
                user_id=user_id,
                report_type=report_type_enum,
                upload_date=datetime.utcnow(),
                status=ReportStatus.PENDING,
                file_path=file_path,
                file_size=len(file_data)
            )
            
            # Save to Firestore
            if self.db:
                await self._save_report_to_firestore(report)
            
            # Start analysis in background
            asyncio.create_task(self._analyze_report(report_id))
            
            logger.info(f"Genetic report uploaded successfully: {report_id}")
            return report_id
            
        except Exception as e:
            logger.error(f"Error uploading genetic report: {e}")
            raise
    
    async def get_genetic_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a genetic report by ID
        """
        try:
            if not self.db:
                return None
            
            doc_ref = self.db.collection('genetic_reports').document(report_id)
            doc = doc_ref.get()
            
            if doc.exists:
                data = doc.to_dict()
                return {
                    "report_id": report_id,
                    "user_id": data.get("user_id"),
                    "report_type": data.get("report_type"),
                    "upload_date": data.get("upload_date"),
                    "analysis_date": data.get("analysis_date"),
                    "status": data.get("status"),
                    "file_path": data.get("file_path"),
                    "file_size": data.get("file_size"),
                    "markers": data.get("markers", []),
                    "crispr_targets": data.get("crispr_targets", []),
                    "summary": data.get("summary", {}),
                    "raw_data": data.get("raw_data", {})
                }
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving genetic report {report_id}: {e}")
            return None
    
    async def get_user_reports(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all genetic reports for a user
        """
        try:
            if not self.db:
                return []
            
            reports_ref = self.db.collection('genetic_reports')
            query = reports_ref.where('user_id', '==', user_id).order_by('upload_date', direction=firestore.Query.DESCENDING)
            docs = query.get()
            
            reports = []
            for doc in docs:
                data = doc.to_dict()
                reports.append({
                    "report_id": doc.id,
                    "user_id": data.get("user_id"),
                    "report_type": data.get("report_type"),
                    "upload_date": data.get("upload_date"),
                    "analysis_date": data.get("analysis_date"),
                    "status": data.get("status"),
                    "file_path": data.get("file_path"),
                    "file_size": data.get("file_size"),
                    "summary": data.get("summary", {})
                })
            
            return reports
            
        except Exception as e:
            logger.error(f"Error retrieving reports for user {user_id}: {e}")
            return []
    
    async def _analyze_report(self, report_id: str):
        """
        Analyze a genetic report in the background
        """
        try:
            # Update status to processing
            await self._update_report_status(report_id, ReportStatus.PROCESSING)
            
            # Get report data
            report_data = await self.get_genetic_report(report_id)
            if not report_data:
                raise Exception("Report not found")
            
            # Download file from storage
            file_data = await self._download_file(report_data["file_path"])
            
            # Parse file content
            parsed_data = await self._parse_file_content(file_data, report_data["report_type"])
            
            # Analyze with AI
            analysis_result = await self._perform_ai_analysis(parsed_data, report_data["report_type"])
            
            # Generate CRISPR targets
            crispr_targets = await self._generate_crispr_targets(analysis_result)
            
            # Create summary
            summary = await self._create_analysis_summary(analysis_result, crispr_targets)
            
            # Update report with results
            await self._update_report_analysis(report_id, analysis_result, crispr_targets, summary)
            
            # Update status to completed
            await self._update_report_status(report_id, ReportStatus.COMPLETED)
            
            logger.info(f"Genetic report analysis completed: {report_id}")
            
        except Exception as e:
            logger.error(f"Error analyzing report {report_id}: {e}")
            await self._update_report_status(report_id, ReportStatus.FAILED)
    
    async def _parse_file_content(self, file_data: bytes, report_type: str) -> Dict[str, Any]:
        """
        Parse different file types and extract genetic data
        """
        try:
            if report_type == ReportType.LAB_REPORT.value:
                return await self._parse_pdf_report(file_data)
            elif report_type == ReportType.VCF_FILE.value:
                return await self._parse_vcf_file(file_data)
            elif report_type == ReportType.FASTA_FILE.value:
                return await self._parse_fasta_file(file_data)
            elif report_type == ReportType.FASTQ_FILE.value:
                return await self._parse_fastq_file(file_data)
            elif report_type == ReportType.GENE_EXPRESSION.value:
                return await self._parse_csv_data(file_data)
            else:
                return await self._parse_generic_text(file_data)
                
        except Exception as e:
            logger.error(f"Error parsing file content: {e}")
            return {"error": str(e)}
    
    async def _parse_pdf_report(self, file_data: bytes) -> Dict[str, Any]:
        """
        Parse PDF lab reports using PyPDF2 and AI
        """
        try:
            # Extract text from PDF
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_data))
            text_content = ""
            for page in pdf_reader.pages:
                text_content += page.extract_text()
            
            # Use AI to extract genetic information
            if self.model:
                prompt = f"""
                Extract genetic information from this lab report. Return JSON with:
                - genetic_markers: list of genetic variants found
                - genes_analyzed: list of genes tested
                - clinical_significance: any clinical findings
                - recommendations: medical recommendations
                
                Report content:
                {text_content[:4000]}
                """
                
                response = self.model.generate_content(prompt)
                try:
                    return json.loads(response.text)
                except:
                    return {"raw_text": text_content, "parsed": False}
            else:
                return {"raw_text": text_content, "parsed": False}
                
        except Exception as e:
            logger.error(f"Error parsing PDF: {e}")
            return {"error": str(e)}
    
    async def _parse_vcf_file(self, file_data: bytes) -> Dict[str, Any]:
        """
        Parse VCF (Variant Call Format) files
        """
        try:
            content = file_data.decode('utf-8')
            lines = content.split('\n')
            
            variants = []
            for line in lines:
                if line.startswith('#') or not line.strip():
                    continue
                
                parts = line.split('\t')
                if len(parts) >= 8:
                    variant = {
                        "chromosome": parts[0],
                        "position": int(parts[1]),
                        "reference": parts[3],
                        "alternate": parts[4],
                        "quality": parts[5],
                        "filter": parts[6],
                        "info": parts[7]
                    }
                    variants.append(variant)
            
            return {
                "file_type": "vcf",
                "variants": variants,
                "total_variants": len(variants)
            }
            
        except Exception as e:
            logger.error(f"Error parsing VCF: {e}")
            return {"error": str(e)}
    
    async def _parse_fasta_file(self, file_data: bytes) -> Dict[str, Any]:
        """
        Parse FASTA sequence files
        """
        try:
            content = file_data.decode('utf-8')
            sequences = {}
            current_header = None
            current_sequence = ""
            
            for line in content.split('\n'):
                if line.startswith('>'):
                    if current_header:
                        sequences[current_header] = current_sequence
                    current_header = line[1:].strip()
                    current_sequence = ""
                else:
                    current_sequence += line.strip()
            
            if current_header:
                sequences[current_header] = current_sequence
            
            return {
                "file_type": "fasta",
                "sequences": sequences,
                "total_sequences": len(sequences)
            }
            
        except Exception as e:
            logger.error(f"Error parsing FASTA: {e}")
            return {"error": str(e)}
    
    async def _parse_fastq_file(self, file_data: bytes) -> Dict[str, Any]:
        """
        Parse FASTQ sequence files
        """
        try:
            content = file_data.decode('utf-8')
            lines = content.split('\n')
            sequences = []
            
            i = 0
            while i < len(lines):
                if lines[i].startswith('@'):
                    if i + 3 < len(lines):
                        sequence = {
                            "header": lines[i][1:],
                            "sequence": lines[i + 1],
                            "quality_header": lines[i + 2],
                            "quality_scores": lines[i + 3]
                        }
                        sequences.append(sequence)
                    i += 4
                else:
                    i += 1
            
            return {
                "file_type": "fastq",
                "sequences": sequences,
                "total_sequences": len(sequences)
            }
            
        except Exception as e:
            logger.error(f"Error parsing FASTQ: {e}")
            return {"error": str(e)}
    
    async def _parse_csv_data(self, file_data: bytes) -> Dict[str, Any]:
        """
        Parse CSV gene expression data
        """
        try:
            df = pd.read_csv(io.BytesIO(file_data))
            return {
                "file_type": "csv",
                "columns": df.columns.tolist(),
                "rows": len(df),
                "data": df.head(100).to_dict('records')  # First 100 rows
            }
            
        except Exception as e:
            logger.error(f"Error parsing CSV: {e}")
            return {"error": str(e)}
    
    async def _parse_generic_text(self, file_data: bytes) -> Dict[str, Any]:
        """
        Parse generic text files
        """
        try:
            content = file_data.decode('utf-8')
            return {
                "file_type": "text",
                "content": content[:10000],  # First 10KB
                "length": len(content)
            }
            
        except Exception as e:
            logger.error(f"Error parsing text: {e}")
            return {"error": str(e)}
    
    async def _perform_ai_analysis(self, parsed_data: Dict[str, Any], report_type: str) -> Dict[str, Any]:
        """
        Perform AI-powered analysis of genetic data
        """
        try:
            if not self.model:
                return {"error": "AI model not available"}
            
            # Create analysis prompt based on data type
            if report_type == ReportType.VCF_FILE.value:
                prompt = self._create_vcf_analysis_prompt(parsed_data)
            elif report_type == ReportType.FASTA_FILE.value:
                prompt = self._create_sequence_analysis_prompt(parsed_data)
            else:
                prompt = self._create_general_analysis_prompt(parsed_data)
            
            response = self.model.generate_content(prompt)
            
            try:
                return json.loads(response.text)
            except:
                return {"raw_analysis": response.text, "parsed": False}
                
        except Exception as e:
            logger.error(f"Error performing AI analysis: {e}")
            return {"error": str(e)}
    
    async def _generate_crispr_targets(self, analysis_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate CRISPR editing targets based on analysis
        """
        try:
            if not self.model:
                return []
            
            prompt = f"""
            Based on this genetic analysis, suggest CRISPR editing targets for therapeutic purposes.
            Return JSON array with:
            - target_id: unique identifier
            - gene_name: target gene
            - target_sequence: DNA sequence to target
            - guide_rna: guide RNA sequence
            - efficiency_score: 0-1 score
            - off_target_risk: low/medium/high
            - therapeutic_potential: description
            - clinical_notes: medical considerations
            
            Analysis: {json.dumps(analysis_result)}
            """
            
            response = self.model.generate_content(prompt)
            
            try:
                targets = json.loads(response.text)
                if isinstance(targets, list):
                    return targets
                else:
                    return []
            except:
                return []
                
        except Exception as e:
            logger.error(f"Error generating CRISPR targets: {e}")
            return []
    
    async def _create_analysis_summary(self, analysis_result: Dict[str, Any], 
                                     crispr_targets: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Create a comprehensive analysis summary
        """
        try:
            if not self.model:
                return {"summary": "Analysis completed without AI enhancement"}
            
            prompt = f"""
            Create a comprehensive summary of this genetic analysis including:
            - key_findings: main genetic discoveries
            - clinical_implications: medical significance
            - risk_assessment: health risks identified
            - recommendations: suggested actions
            - crispr_opportunities: therapeutic possibilities
            
            Analysis: {json.dumps(analysis_result)}
            CRISPR Targets: {json.dumps(crispr_targets)}
            """
            
            response = self.model.generate_content(prompt)
            
            try:
                return json.loads(response.text)
            except:
                return {"summary": response.text}
                
        except Exception as e:
            logger.error(f"Error creating summary: {e}")
            return {"error": str(e)}
    
    def _detect_report_type(self, filename: str, file_data: bytes) -> str:
        """
        Detect the type of genetic report based on filename and content
        """
        filename_lower = filename.lower()
        
        if filename_lower.endswith('.pdf'):
            return ReportType.LAB_REPORT.value
        elif filename_lower.endswith('.vcf'):
            return ReportType.VCF_FILE.value
        elif filename_lower.endswith('.fasta') or filename_lower.endswith('.fa'):
            return ReportType.FASTA_FILE.value
        elif filename_lower.endswith('.fastq') or filename_lower.endswith('.fq'):
            return ReportType.FASTQ_FILE.value
        elif filename_lower.endswith('.csv'):
            return ReportType.GENE_EXPRESSION.value
        else:
            return ReportType.UNKNOWN.value
    
    def _get_content_type(self, filename: str) -> str:
        """
        Get MIME content type for file
        """
        filename_lower = filename.lower()
        
        if filename_lower.endswith('.pdf'):
            return 'application/pdf'
        elif filename_lower.endswith('.vcf'):
            return 'text/plain'
        elif filename_lower.endswith('.fasta') or filename_lower.endswith('.fa'):
            return 'text/plain'
        elif filename_lower.endswith('.fastq') or filename_lower.endswith('.fq'):
            return 'text/plain'
        elif filename_lower.endswith('.csv'):
            return 'text/csv'
        else:
            return 'application/octet-stream'
    
    async def _save_report_to_firestore(self, report: GeneticReport):
        """
        Save report to Firestore
        """
        try:
            doc_ref = self.db.collection('genetic_reports').document(report.report_id)
            doc_ref.set({
                'report_id': report.report_id,
                'user_id': report.user_id,
                'report_type': report.report_type.value,
                'upload_date': firestore.SERVER_TIMESTAMP,
                'analysis_date': None,
                'status': report.status.value,
                'file_path': report.file_path,
                'file_size': report.file_size,
                'markers': [],
                'crispr_targets': [],
                'summary': {},
                'raw_data': {}
            })
        except Exception as e:
            logger.error(f"Error saving report to Firestore: {e}")
    
    async def _update_report_status(self, report_id: str, status: ReportStatus):
        """
        Update report status in Firestore
        """
        try:
            if self.db:
                doc_ref = self.db.collection('genetic_reports').document(report_id)
                doc_ref.update({
                    'status': status.value,
                    'analysis_date': firestore.SERVER_TIMESTAMP if status == ReportStatus.COMPLETED else None
                })
        except Exception as e:
            logger.error(f"Error updating report status: {e}")
    
    async def _update_report_analysis(self, report_id: str, analysis_result: Dict[str, Any],
                                    crispr_targets: List[Dict[str, Any]], summary: Dict[str, Any]):
        """
        Update report with analysis results
        """
        try:
            if self.db:
                doc_ref = self.db.collection('genetic_reports').document(report_id)
                doc_ref.update({
                    'markers': analysis_result.get('genetic_markers', []),
                    'crispr_targets': crispr_targets,
                    'summary': summary,
                    'raw_data': analysis_result
                })
        except Exception as e:
            logger.error(f"Error updating report analysis: {e}")
    
    async def _download_file(self, file_path: str) -> bytes:
        """
        Download file from Firebase Storage
        """
        try:
            if not self.bucket:
                logger.warning("Firebase Storage not available. Cannot download file.")
                return b""  # Return empty bytes for memory-only files
            
            blob = self.bucket.blob(file_path)
            return blob.download_as_bytes()
        except Exception as e:
            logger.error(f"Error downloading file {file_path}: {e}")
            raise
    
    def _create_vcf_analysis_prompt(self, parsed_data: Dict[str, Any]) -> str:
        """
        Create analysis prompt for VCF files
        """
        variants = parsed_data.get('variants', [])
        return f"""
        Analyze these genetic variants from a VCF file. Return JSON with:
        - genetic_markers: list of significant variants with gene names and clinical impact
        - risk_variants: variants with potential health risks
        - benign_variants: harmless variants
        - clinical_recommendations: medical advice based on findings
        
        Variants: {json.dumps(variants[:50])}  # First 50 variants
        """
    
    def _create_sequence_analysis_prompt(self, parsed_data: Dict[str, Any]) -> str:
        """
        Create analysis prompt for sequence files
        """
        sequences = parsed_data.get('sequences', {})
        return f"""
        Analyze these DNA/RNA sequences. Return JSON with:
        - sequence_analysis: quality and characteristics
        - potential_mutations: any notable variations
        - gene_identification: genes that might be present
        - clinical_insights: medical implications
        
        Sequences: {json.dumps(list(sequences.items())[:10])}  # First 10 sequences
        """
    
    def _create_general_analysis_prompt(self, parsed_data: Dict[str, Any]) -> str:
        """
        Create general analysis prompt for other file types
        """
        return f"""
        Analyze this genetic data. Return JSON with:
        - key_findings: main discoveries
        - genetic_markers: any genetic variants found
        - clinical_significance: medical implications
        - recommendations: suggested actions
        
        Data: {json.dumps(parsed_data)}
        """
    
    # New methods for enhanced functionality
    
    async def process_genetic_report_from_frontend(self, user_id: str, file_content: str, 
                                                 filename: str, report_type: str = "unknown") -> Dict[str, Any]:
        """
        Process genetic report uploaded from frontend (Flutter app)
        This method handles the file content sent from the frontend
        """
        try:
            # Convert string content to bytes
            file_data = file_content.encode('utf-8')
            
            # Upload and process the report
            report_id = await self.upload_genetic_report(user_id, file_data, filename, report_type)
            
            # Wait for analysis to complete (with timeout)
            analysis_complete = await self._wait_for_analysis_completion(report_id, timeout=300)  # 5 minutes
            
            if analysis_complete:
                # Get the completed report
                report_data = await self.get_genetic_report(report_id)
                if report_data:
                    # Update user's genetic data in MCP system
                    await self._update_user_genetic_context(user_id, report_data)
                    
                    return {
                        'success': True,
                        'report_id': report_id,
                        'analysis_data': {
                            'genes_analyzed': len(report_data.get('markers', [])),
                            'risk_factors': self._extract_risk_factors(report_data),
                            'recommendations': self._extract_recommendations(report_data),
                            'confidence_score': self._calculate_confidence_score(report_data),
                            'crispr_targets_count': len(report_data.get('crispr_targets', [])),
                            'summary': report_data.get('summary', {})
                        }
                    }
            
            # If analysis is still pending, return status
            return {
                'success': True,
                'report_id': report_id,
                'status': 'processing',
                'message': 'Genetic report uploaded and analysis started. Results will be available shortly.'
            }
            
        except Exception as e:
            logger.error(f"Error processing genetic report from frontend: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _wait_for_analysis_completion(self, report_id: str, timeout: int = 300) -> bool:
        """
        Wait for analysis to complete with timeout
        """
        start_time = datetime.utcnow()
        while (datetime.utcnow() - start_time).seconds < timeout:
            report_data = await self.get_genetic_report(report_id)
            if report_data and report_data.get('status') == ReportStatus.COMPLETED.value:
                return True
            elif report_data and report_data.get('status') == ReportStatus.FAILED.value:
                return False
            await asyncio.sleep(5)  # Check every 5 seconds
        return False
    
    async def _update_user_genetic_context(self, user_id: str, report_data: Dict[str, Any]):
        """
        Update user's genetic context in the MCP system for enhanced LLM responses
        """
        try:
            if not self.db:
                return
            
            # Create genetic context summary
            genetic_context = {
                'user_id': user_id,
                'last_updated': datetime.utcnow().isoformat(),
                'genetic_markers': report_data.get('markers', []),
                'risk_factors': self._extract_risk_factors(report_data),
                'clinical_significance': self._extract_clinical_significance(report_data),
                'recommendations': self._extract_recommendations(report_data),
                'crispr_targets': report_data.get('crispr_targets', []),
                'summary': report_data.get('summary', {}),
                'report_type': report_data.get('report_type'),
                'analysis_date': report_data.get('analysis_date')
            }
            
            # Save to user's genetic context collection
            await self.db.collection('patients').document(user_id).collection('genetic_context').document('latest').set(genetic_context)
            
            # Also update the main patient document with genetic summary
            await self.db.collection('patients').document(user_id).update({
                'genetic_context': {
                    'has_genetic_data': True,
                    'last_analysis_date': report_data.get('analysis_date'),
                    'risk_factors': genetic_context['risk_factors'],
                    'key_recommendations': genetic_context['recommendations'][:3] if genetic_context['recommendations'] else [],
                    'markers_count': len(genetic_context['genetic_markers'])
                }
            })
            
            logger.info(f"Updated genetic context for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error updating genetic context for user {user_id}: {e}")
    
    def _extract_risk_factors(self, report_data: Dict[str, Any]) -> List[str]:
        """
        Extract risk factors from genetic analysis
        """
        risk_factors = []
        
        # Extract from markers
        markers = report_data.get('markers', [])
        for marker in markers:
            if isinstance(marker, dict) and marker.get('significance') in ['pathogenic', 'likely_pathogenic']:
                gene_name = marker.get('gene_name', 'Unknown gene')
                clinical_impact = marker.get('clinical_impact', '')
                risk_factors.append(f"{gene_name}: {clinical_impact}")
        
        # Extract from summary
        summary = report_data.get('summary', {})
        if isinstance(summary, dict):
            risk_assessment = summary.get('risk_assessment', [])
            if isinstance(risk_assessment, list):
                risk_factors.extend(risk_assessment)
            elif isinstance(risk_assessment, str):
                risk_factors.append(risk_assessment)
        
        return list(set(risk_factors))  # Remove duplicates
    
    def _extract_clinical_significance(self, report_data: Dict[str, Any]) -> List[str]:
        """
        Extract clinical significance from genetic analysis
        """
        clinical_significance = []
        
        # Extract from summary
        summary = report_data.get('summary', {})
        if isinstance(summary, dict):
            clinical_implications = summary.get('clinical_implications', [])
            if isinstance(clinical_implications, list):
                clinical_significance.extend(clinical_implications)
            elif isinstance(clinical_implications, str):
                clinical_significance.append(clinical_implications)
        
        # Extract from markers
        markers = report_data.get('markers', [])
        for marker in markers:
            if isinstance(marker, dict) and marker.get('clinical_impact'):
                clinical_significance.append(marker['clinical_impact'])
        
        return list(set(clinical_significance))  # Remove duplicates
    
    def _extract_recommendations(self, report_data: Dict[str, Any]) -> List[str]:
        """
        Extract recommendations from genetic analysis
        """
        recommendations = []
        
        # Extract from summary
        summary = report_data.get('summary', {})
        if isinstance(summary, dict):
            summary_recommendations = summary.get('recommendations', [])
            if isinstance(summary_recommendations, list):
                recommendations.extend(summary_recommendations)
            elif isinstance(summary_recommendations, str):
                recommendations.append(summary_recommendations)
        
        # Extract from raw data
        raw_data = report_data.get('raw_data', {})
        if isinstance(raw_data, dict):
            raw_recommendations = raw_data.get('recommendations', [])
            if isinstance(raw_recommendations, list):
                recommendations.extend(raw_recommendations)
            elif isinstance(raw_recommendations, str):
                recommendations.append(raw_recommendations)
        
        return list(set(recommendations))  # Remove duplicates
    
    def _calculate_confidence_score(self, report_data: Dict[str, Any]) -> float:
        """
        Calculate confidence score for genetic analysis
        """
        try:
            markers = report_data.get('markers', [])
            if not markers:
                return 0.5  # Default confidence
            
            # Calculate based on marker quality and quantity
            total_markers = len(markers)
            high_confidence_markers = sum(1 for m in markers if isinstance(m, dict) and m.get('confidence_score', 0) > 0.7)
            
            if total_markers == 0:
                return 0.5
            
            base_confidence = min(0.9, 0.5 + (total_markers / 100))  # More markers = higher confidence
            quality_boost = (high_confidence_markers / total_markers) * 0.3
            
            return min(0.95, base_confidence + quality_boost)
            
        except Exception as e:
            logger.error(f"Error calculating confidence score: {e}")
            return 0.5
    
    async def get_user_genetic_context(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user's genetic context for LLM integration
        """
        try:
            if not self.db:
                return None
            
            # Get latest genetic context
            doc_ref = self.db.collection('patients').document(user_id).collection('genetic_context').document('latest')
            doc = doc_ref.get()
            
            if doc.exists:
                return doc.to_dict()
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting genetic context for user {user_id}: {e}")
            return None
    
    async def get_genetic_insights_for_llm(self, user_id: str) -> Dict[str, Any]:
        """
        Get formatted genetic insights for LLM prompt enhancement
        """
        try:
            genetic_context = await self.get_user_genetic_context(user_id)
            if not genetic_context:
                return {}
            
            return {
                'has_genetic_data': True,
                'risk_factors': genetic_context.get('risk_factors', []),
                'clinical_significance': genetic_context.get('clinical_significance', []),
                'recommendations': genetic_context.get('recommendations', []),
                'key_findings': genetic_context.get('summary', {}).get('key_findings', []),
                'crispr_opportunities': genetic_context.get('summary', {}).get('crispr_opportunities', []),
                'last_analysis_date': genetic_context.get('last_updated'),
                'markers_count': len(genetic_context.get('genetic_markers', [])),
                'crispr_targets_count': len(genetic_context.get('crispr_targets', []))
            }
            
        except Exception as e:
            logger.error(f"Error getting genetic insights for LLM: {e}")
            return {}
    
    async def delete_genetic_report(self, user_id: str, report_id: str) -> bool:
        """
        Delete a genetic report and its associated data
        """
        try:
            if not self.db:
                return False
            
            # Get report data first
            report_data = await self.get_genetic_report(report_id)
            if not report_data or report_data.get('user_id') != user_id:
                return False
            
            # Delete from Firestore
            await self.db.collection('genetic_reports').document(report_id).delete()
            
            # Delete from Firebase Storage
            try:
                if self.bucket and report_data.get('file_path') and report_data.get('file_path') != 'memory_only':
                    blob = self.bucket.blob(report_data.get('file_path', ''))
                    blob.delete()
                    logger.info(f"File deleted from Firebase Storage: {report_data.get('file_path')}")
                else:
                    logger.info("No file to delete from storage (memory-only or no storage available)")
            except Exception as e:
                logger.warning(f"Could not delete file from storage: {e}")
            
            # Update user's genetic context if this was the latest report
            await self._update_user_genetic_context_after_deletion(user_id)
            
            logger.info(f"Deleted genetic report {report_id} for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting genetic report {report_id}: {e}")
            return False
    
    async def _update_user_genetic_context_after_deletion(self, user_id: str):
        """
        Update user's genetic context after report deletion
        """
        try:
            if not self.db:
                return
            
            # Get remaining reports
            remaining_reports = await self.get_user_reports(user_id)
            
            if remaining_reports:
                # Update with latest report data
                latest_report = remaining_reports[0]  # Already sorted by date
                report_data = await self.get_genetic_report(latest_report['report_id'])
                if report_data:
                    await self._update_user_genetic_context(user_id, report_data)
            else:
                # No reports left, clear genetic context
                await self.db.collection('patients').document(user_id).update({
                    'genetic_context': {
                        'has_genetic_data': False,
                        'last_analysis_date': None,
                        'risk_factors': [],
                        'key_recommendations': [],
                        'markers_count': 0
                    }
                })
                
                # Clear genetic context collection
                await self.db.collection('patients').document(user_id).collection('genetic_context').document('latest').delete()
            
        except Exception as e:
            logger.error(f"Error updating genetic context after deletion: {e}")
    
    async def get_genetic_summary_for_patient(self, user_id: str) -> Dict[str, Any]:
        """
        Get a comprehensive genetic summary for a patient
        """
        try:
            genetic_context = await self.get_user_genetic_context(user_id)
            if not genetic_context:
                return {
                    'has_genetic_data': False,
                    'message': 'No genetic data available'
                }
            
            return {
                'has_genetic_data': True,
                'last_analysis_date': genetic_context.get('last_updated'),
                'total_markers': len(genetic_context.get('genetic_markers', [])),
                'risk_factors_count': len(genetic_context.get('risk_factors', [])),
                'recommendations_count': len(genetic_context.get('recommendations', [])),
                'crispr_targets_count': len(genetic_context.get('crispr_targets', [])),
                'key_risk_factors': genetic_context.get('risk_factors', [])[:5],  # Top 5
                'key_recommendations': genetic_context.get('recommendations', [])[:5],  # Top 5
                'clinical_significance': genetic_context.get('clinical_significance', [])[:3],  # Top 3
                'summary': genetic_context.get('summary', {})
            }
            
        except Exception as e:
            logger.error(f"Error getting genetic summary for patient {user_id}: {e}")
            return {
                'has_genetic_data': False,
                'error': str(e)
            }

# Global instance for easy access
genetic_analysis_service = GeneticAnalysisService() 