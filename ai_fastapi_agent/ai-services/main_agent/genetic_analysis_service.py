import os
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import json
import uuid
import io

# File processing
import PyPDF2
import pandas as pd

# Google Cloud imports
from google.cloud import storage
from firebase_admin import firestore

# Hugging Face
from huggingface_hub import InferenceClient
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# -------------------
# Enums
# -------------------
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

# -------------------
# Data Classes
# -------------------
@dataclass
class GeneticMarker:
    marker_id: str
    gene_name: str
    chromosome: Optional[str] = None
    position: Optional[int] = None
    reference_allele: Optional[str] = None
    alternate_allele: Optional[str] = None
    significance: Optional[str] = None
    clinical_impact: Optional[str] = None
    frequency: Optional[float] = None
    confidence_score: Optional[float] = None

@dataclass
class CRISPRTarget:
    target_id: str
    gene_name: str
    target_sequence: str
    guide_rna: str
    efficiency_score: float
    off_target_risk: str
    therapeutic_potential: str
    clinical_notes: str

@dataclass
class GeneticReport:
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

# -------------------
# Genetic Analysis Service
# -------------------
class GeneticAnalysisService:
    def __init__(self, db: firestore.client = None, storage_client: storage.Client = None):
        self.db = db
        # Use existing Firebase collections instead of separate storage
        self.storage_client = None
        self.bucket = None
        logger.info("Genetic Analysis Service using Firebase collections (no separate storage)")

        # Hugging Face Medical NER client
        try:
            hf_token = os.environ.get("HF_TOKEN")
            if hf_token:
                self.hf_client = InferenceClient(token=hf_token)
                logger.info("Hugging Face InferenceClient initialized with medical model")
            else:
                self.hf_client = None
                logger.warning("HF_TOKEN not found - genetic analysis will use fallback responses")
        except Exception as e:
            self.hf_client = None
            logger.warning(f"Hugging Face client not initialized: {e}")

    def _detect_report_type(self, filename: str, file_data: bytes) -> str:
        try:
            name = (filename or "").lower()
            if name.endswith(".vcf"):
                return ReportType.VCF_FILE.value
            if name.endswith(".fasta") or name.endswith(".fa"):
                return ReportType.FASTA_FILE.value
            if name.endswith(".fastq") or name.endswith(".fq"):
                return ReportType.FASTQ_FILE.value
            if name.endswith(".pdf"):
                return ReportType.LAB_REPORT.value
            # Heuristic on content
            try:
                text = file_data[:64].decode("utf-8", errors="ignore")
                if text.startswith("##fileformat=VCF"):
                    return ReportType.VCF_FILE.value
                if text.startswith(">"):
                    return ReportType.FASTA_FILE.value
                if text.startswith("@"):
                    return ReportType.FASTQ_FILE.value
            except Exception:
                pass
            return ReportType.UNKNOWN.value
        except Exception:
            return ReportType.UNKNOWN.value

    # -------------------
    # Upload & Parse
    # -------------------
    async def analyze_file_serverless(self, user_id: str, file_data: bytes, filename: str, report_type: str = "unknown") -> Dict[str, Any]:
        """
        Serverless file analysis - parse file in memory and get HF inference directly
        No file storage, no Firestore writes - pure serverless processing
        """
        try:
            detected_type = self._detect_report_type(filename, file_data)
            logger.info(f"Analyzing {filename} ({detected_type}) for user {user_id} - serverless mode")
            
            # Parse file content in memory
            parsed_data = await self._parse_file_content(file_data, detected_type)
            
            # Get HF medical model analysis
            analysis_result = await self._perform_ai_analysis(parsed_data, detected_type)
            
            # Return immediate results
            return {
                "status": "success",
                "message": f"Medical analysis completed for {filename}",
                "user_id": user_id,
                "filename": filename,
                "file_type": detected_type,
                "file_size": len(file_data),
                "analysis": {
                    "genetic_markers": analysis_result.get("genetic_markers", []),
                    "genes_analyzed": analysis_result.get("genes_analyzed", []),
                    "clinical_significance": analysis_result.get("clinical_significance", []),
                    "summary": f"Found {len(analysis_result.get('genetic_markers', []))} genetic markers and {len(analysis_result.get('genes_analyzed', []))} genes"
                },
                "raw_ner_output": analysis_result.get("raw_ner_output", []),
                "processed_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in serverless analysis: {e}")
            return {
                "status": "error",
                "message": f"Analysis failed: {str(e)}",
                "user_id": user_id,
                "filename": filename,
                "error": str(e)
            }

    async def upload_genetic_report(self, user_id: str, file_data: bytes, filename: str, report_type: str = "unknown") -> str:
        """
        Legacy upload method - now redirects to serverless analysis
        """
        try:
            result = await self.analyze_file_serverless(user_id, file_data, filename, report_type)
            
            # Only store minimal metadata in Firestore if needed
            if self.db and result["status"] == "success":
                report_id = str(uuid.uuid4())
                minimal_record = {
                    "report_id": report_id,
                    "user_id": user_id,
                    "filename": filename,
                    "file_type": result["file_type"],
                    "analysis_summary": result["analysis"]["summary"],
                    "markers_count": len(result["analysis"]["genetic_markers"]),
                    "genes_count": len(result["analysis"]["genes_analyzed"]),
                    "processed_at": firestore.SERVER_TIMESTAMP,
                    "status": "completed"
                }
                
                self.db.collection("genetic_analysis_results").document(report_id).set(minimal_record)
                return report_id
            else:
                return result.get("message", "Analysis completed")
                
        except Exception as e:
            logger.error(f"Error in upload_genetic_report: {e}")
            return f"Error: {str(e)}"

    async def _analyze_report(self, report_id: str):
        try:
            await self._update_report_status(report_id, ReportStatus.PROCESSING)
            report_data = await self.get_genetic_report(report_id)
            if not report_data:
                raise Exception("Report not found")

            file_data = await self._download_file(report_data["file_path"])
            parsed_data = await self._parse_file_content(file_data, report_data["report_type"])
            analysis_result = await self._perform_ai_analysis(parsed_data, report_data["report_type"])
            # Placeholder for CRISPR targets
            crispr_targets = []
            summary = {"summary": "AI analysis completed via Hugging Face NER"}
            await self._update_report_analysis(report_id, analysis_result, crispr_targets, summary)
            await self._update_report_status(report_id, ReportStatus.COMPLETED)
            logger.info(f"Report analysis completed: {report_id}")
        except Exception as e:
            logger.error(f"Error analyzing report {report_id}: {e}")
            await self._update_report_status(report_id, ReportStatus.FAILED)

    # -------------------
    # File Parsing
    # -------------------
    async def _parse_file_content(self, file_data: bytes, report_type: str) -> Dict[str, Any]:
        try:
            if report_type == ReportType.LAB_REPORT.value:
                return await self._parse_pdf_report(file_data)
            elif report_type == ReportType.VCF_FILE.value:
                return await self._parse_vcf_file(file_data)
            elif report_type == ReportType.FASTA_FILE.value:
                return await self._parse_fasta_file(file_data)
            elif report_type == ReportType.FASTQ_FILE.value:
                return await self._parse_fastq_file(file_data)
            else:
                return await self._parse_generic_text(file_data)
        except Exception as e:
            logger.error(f"Error parsing file content: {e}")
            return {"error": str(e)}

    # -------------------
    # PDF, VCF, Text Parsing
    # -------------------
    async def _parse_pdf_report(self, file_data: bytes) -> Dict[str, Any]:
        try:
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_data))
            text_content = ""
            for page in pdf_reader.pages:
                text_content += page.extract_text() or ""
            return {"raw_text": text_content[:5000]}  # truncate to 5k chars
        except Exception as e:
            logger.error(f"Error parsing PDF: {e}")
            return {"error": str(e)}

    async def _parse_vcf_file(self, file_data: bytes) -> Dict[str, Any]:
        try:
            content = file_data.decode("utf-8")
            lines = content.split("\n")
            variants = []
            for line in lines:
                if line.startswith("#") or not line.strip():
                    continue
                parts = line.split("\t")
                if len(parts) >= 8:
                    variants.append({
                        "chromosome": parts[0],
                        "position": int(parts[1]),
                        "reference": parts[3],
                        "alternate": parts[4],
                        "info": parts[7]
                    })
            return {"variants": variants}
        except Exception as e:
            logger.error(f"Error parsing VCF: {e}")
            return {"error": str(e)}

    async def _parse_generic_text(self, file_data: bytes) -> Dict[str, Any]:
        try:
            content = file_data.decode("utf-8")
            return {"raw_text": content[:5000]}
        except Exception as e:
            logger.error(f"Error parsing text: {e}")
            return {"error": str(e)}

    # -------------------
    # FASTA & FASTQ Parsing with HF NER
    # -------------------
    async def _parse_fasta_file(self, file_data: bytes) -> Dict[str, Any]:
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

            seq_text = " ".join(list(sequences.values())[:5])
            ner_results = self.hf_client.token_classification(seq_text, model="OpenMed/OpenMed-NER-GenomeDetect-SuperClinical-434M") if self.hf_client else []

            analysis_result = {
                "file_type": "fasta",
                "sequences_count": len(sequences),
                "genetic_markers": [],
                "genes_analyzed": [],
                "clinical_significance": [],
                "raw_ner_output": ner_results
            }
            for entity in ner_results:
                label = entity.get("entity_group")
                word = entity.get("word")
                if label in ["GENE", "VARIANT"]:
                    analysis_result["genetic_markers"].append({"gene_name": word, "type": label})
                elif label == "DISEASE":
                    analysis_result["clinical_significance"].append(word)
                if label == "GENE" and word not in analysis_result["genes_analyzed"]:
                    analysis_result["genes_analyzed"].append(word)
            return analysis_result
        except Exception as e:
            logger.error(f"Error parsing FASTA: {e}")
            return {"error": str(e)}

    async def _parse_fastq_file(self, file_data: bytes) -> Dict[str, Any]:
        try:
            content = file_data.decode('utf-8')
            lines = content.split('\n')
            sequences = []
            i = 0
            while i < len(lines):
                if lines[i].startswith('@'):
                    if i + 3 < len(lines):
                        sequences.append(lines[i + 1])
                    i += 4
                else:
                    i += 1
            seq_text = " ".join(sequences[:5])
            ner_results = self.hf_client.token_classification(seq_text, model="OpenMed/OpenMed-NER-GenomeDetect-SuperClinical-434M") if self.hf_client else []

            analysis_result = {
                "file_type": "fastq",
                "sequences_count": len(sequences),
                "genetic_markers": [],
                "genes_analyzed": [],
                "clinical_significance": [],
                "raw_ner_output": ner_results
            }
            for entity in ner_results:
                label = entity.get("entity_group")
                word = entity.get("word")
                if label in ["GENE", "VARIANT"]:
                    analysis_result["genetic_markers"].append({"gene_name": word, "type": label})
                elif label == "DISEASE":
                    analysis_result["clinical_significance"].append(word)
                if label == "GENE" and word not in analysis_result["genes_analyzed"]:
                    analysis_result["genes_analyzed"].append(word)
            return analysis_result
        except Exception as e:
            logger.error(f"Error parsing FASTQ: {e}")
            return {"error": str(e)}

    # -------------------
    # HF NER Analysis for others
    # -------------------
    async def _perform_ai_analysis(self, parsed_data: Dict[str, Any], report_type: str) -> Dict[str, Any]:
        try:
            if not self.hf_client:
                return {
                    "genetic_markers": [],
                    "genes_analyzed": [],
                    "clinical_significance": [],
                    "raw_ner_output": [],
                    "warning": "HF client not initialized"
                }

            if report_type in [ReportType.LAB_REPORT.value, ReportType.UNKNOWN.value]:
                text_input = parsed_data.get("raw_text", "")
            elif report_type == ReportType.VCF_FILE.value:
                variants = parsed_data.get("variants", [])
                text_input = "\n".join([f"{v['chromosome']}:{v['position']} {v['reference']}>{v['alternate']}" for v in variants])
            else:
                text_input = str(parsed_data)[:1000]

            ner_results = self.hf_client.token_classification(
                text_input,
                model="OpenMed/OpenMed-NER-GenomeDetect-SuperClinical-434M"
            )

            analysis_result = {"genetic_markers": [], "genes_analyzed": [], "clinical_significance": [], "raw_ner_output": ner_results}
            for entity in ner_results:
                label = entity.get("entity_group")
                word = entity.get("word")
                if label in ["GENE", "VARIANT"]:
                    analysis_result["genetic_markers"].append({"gene_name": word, "type": label})
                elif label == "DISEASE":
                    analysis_result["clinical_significance"].append(word)
                if label == "GENE" and word not in analysis_result["genes_analyzed"]:
                    analysis_result["genes_analyzed"].append(word)
            return analysis_result
        except Exception as e:
            logger.error(f"Error performing HF NER analysis: {e}")
            return {
                "genetic_markers": [],
                "genes_analyzed": [],
                "clinical_significance": [],
                "raw_ner_output": [],
                "error": str(e)
            }

    # -------------------
    # Firestore & Storage Helpers
    # -------------------
    async def _save_report_to_firestore(self, report: GeneticReport, file_content: str = ""):
        try:
            doc_ref = self.db.collection("genetic_reports").document(report.report_id)
            doc_ref.set({
                "report_id": report.report_id,
                "user_id": report.user_id,
                "report_type": report.report_type.value,
                "upload_date": firestore.SERVER_TIMESTAMP,
                "analysis_date": None,
                "status": report.status.value,
                "file_path": report.file_path,
                "file_size": report.file_size,
                "file_content": file_content[:5000] if file_content else "",  # Store limited content for analysis
                "markers": [],
                "crispr_targets": [],
                "summary": {},
                "raw_data": {}
            })
        except Exception as e:
            logger.error(f"Error saving report: {e}")

    async def _update_report_status(self, report_id: str, status: ReportStatus):
        try:
            if self.db:
                doc_ref = self.db.collection("genetic_reports").document(report_id)
                doc_ref.update({
                    "status": status.value,
                    "analysis_date": firestore.SERVER_TIMESTAMP if status == ReportStatus.COMPLETED else None
                })
        except Exception as e:
            logger.error(f"Error updating report status: {e}")

    async def _update_report_analysis(self, report_id: str, analysis_result: Dict[str, Any], crispr_targets: List[Dict[str, Any]], summary: Dict[str, Any]):
        try:
            if self.db:
                doc_ref = self.db.collection("genetic_reports").document(report_id)
                doc_ref.update({
                    "markers": analysis_result.get("genetic_markers", []),
                    "crispr_targets": crispr_targets,
                    "summary": summary,
                    "raw_data": analysis_result
                })
        except Exception as e:
            logger.error(f"Error updating report analysis: {e}")

    async def get_genetic_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        try:
            if not self.db:
                return None
            doc_ref = self.db.collection("genetic_reports").document(report_id)
            doc = doc_ref.get()
            if doc.exists:
                return doc.to_dict()
            return None
        except Exception as e:
            logger.error(f"Error getting report {report_id}: {e}")
            return None

    async def get_user_reports(self, user_id: str) -> List[Dict[str, Any]]:
        try:
            if not self.db:
                return []
            col = self.db.collection("genetic_analysis_results")
            query = col.where("user_id", "==", user_id).order_by("processed_at", direction=firestore.Query.DESCENDING).limit(50)
            docs = query.get()
            results: List[Dict[str, Any]] = []
            for d in docs:
                item = d.to_dict()
                item["id"] = d.id
                results.append(item)
            return results
        except Exception as e:
            logger.warning(f"Failed to get user reports: {e}")
            return []

    async def get_genetic_insights_for_llm(self, user_id: str) -> Dict[str, Any]:
        try:
            reports = await self.get_user_reports(user_id)
            if not reports:
                return {"has_genetic_data": False}
            latest = reports[0]
            return {
                "has_genetic_data": True,
                "markers_count": latest.get("markers_count", 0),
                "genes_count": latest.get("genes_count", 0),
                "analysis_summary": latest.get("analysis_summary"),
                "last_analysis_date": latest.get("processed_at"),
                "risk_factors": [],
                "clinical_significance": [],
                "key_findings": [],
                "crispr_opportunities": [],
            }
        except Exception as e:
            logger.warning(f"Failed to build genetic insights: {e}")
            return {"has_genetic_data": False, "error": str(e)}

    async def _download_file(self, file_path: str) -> bytes:
        if not self.bucket or file_path == "memory_only":
            return b""
        blob = self.bucket.blob(file_path)
        return blob.download_as_bytes()

# -------------------
# Global instance
# -------------------
genetic_analysis_service = GeneticAnalysisService()
