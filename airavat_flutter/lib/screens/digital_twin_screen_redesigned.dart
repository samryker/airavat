import 'package:flutter/material.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:file_picker/file_picker.dart';
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:lottie/lottie.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import '../services/api_service.dart';

/// Modern redesigned Digital Twin screen matching the provided UI mockup
/// Features:
/// - Dark medical theme
/// - 3D body visualization
/// - Autonomous agent lab report analysis
/// - Lottie animations during processing
/// - Save to Firestore functionality
class DigitalTwinScreenRedesigned extends StatefulWidget {
  const DigitalTwinScreenRedesigned({super.key});

  @override
  State<DigitalTwinScreenRedesigned> createState() =>
      _DigitalTwinScreenRedesignedState();
}

class _DigitalTwinScreenRedesignedState
    extends State<DigitalTwinScreenRedesigned> with TickerProviderStateMixin {
  // State variables
  bool _isProcessing = false;
  bool _hasResults = false;
  String? _selectedFileName;
  PlatformFile? _selectedFile;

  // Analysis results
  String? _confidenceScore;
  String? _severity;
  String? _priority;
  String? _primaryAnalysis;
  String? _medicalInferences;
  String? _proactiveRecommendations;
  String? _fullAnalysis;

  // Animation controller
  late AnimationController _fadeController;
  late Animation<double> _fadeAnimation;

  // Medical facts for animation display
  final List<String> _medicalFacts = [
    "AI is analyzing your biomarkers...",
    "Processing genetic markers...",
    "Evaluating health patterns...",
    "Generating personalized insights...",
    "Calculating confidence scores...",
    "Identifying potential health risks...",
    "Formulating recommendations...",
    "Medical AI can detect patterns humans might miss",
    "Digital twins enable predictive healthcare",
    "Personalized medicine is the future of healthcare"
  ];

  int _currentFactIndex = 0;

  @override
  void initState() {
    super.initState();
    _fadeController = AnimationController(
      duration: const Duration(milliseconds: 600),
      vsync: this,
    );
    _fadeAnimation =
        Tween<double>(begin: 0.0, end: 1.0).animate(_fadeController);
  }

  @override
  void dispose() {
    _fadeController.dispose();
    super.dispose();
  }

  Future<void> _pickFile() async {
    try {
      FilePickerResult? result = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['pdf', 'txt', 'doc', 'docx', 'jpg', 'jpeg', 'png'],
        withData: true,
      );

      if (result != null) {
        setState(() {
          _selectedFile = result.files.first;
          _selectedFileName = result.files.first.name;
        });
      }
    } catch (e) {
      _showSnackBar('Error picking file: $e', isError: true);
    }
  }

  Future<void> _analyzeLabReport() async {
    if (_selectedFile == null) {
      _showSnackBar('Please select a file first', isError: true);
      return;
    }

    final user = FirebaseAuth.instance.currentUser;
    if (user == null) {
      _showSnackBar('Please login first', isError: true);
      return;
    }

    setState(() {
      _isProcessing = true;
      _hasResults = false;
      _currentFactIndex = 0;
    });

    // Cycle through medical facts during processing
    _startFactRotation();

    try {
      final baseUrl = ApiService.baseUrl;
      // Use existing, established backend endpoint to avoid new routes
      final uri = Uri.parse('$baseUrl/upload/analyze');

      // Create multipart request
      var request = http.MultipartRequest('POST', uri);
      request.files.add(http.MultipartFile.fromBytes(
        'file',
        _selectedFile!.bytes!,
        filename: _selectedFileName,
      ));
      // Provide required form fields expected by existing endpoint
      request.fields['patient_id'] = user.uid;
      request.fields['file_type'] = 'lab_report';

      // Send request
      final streamedResponse = await request.send();
      final response = await http.Response.fromStream(streamedResponse);

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        // Existing endpoint returns a wrapper with gemini_response text
        final String rawText =
            data['file_analysis']?['gemini_response']?.toString() ?? '';
        final parsed = _parseGeminiText(rawText);

        setState(() {
          _confidenceScore = parsed['confidence_score'].toString();
          _severity = parsed['severity'];
          _priority = parsed['priority'];
          _primaryAnalysis = parsed['primary_analysis'];
          _medicalInferences = parsed['medical_inferences'];
          _proactiveRecommendations = parsed['proactive_recommendations'];
          _fullAnalysis = parsed['full_analysis'];
          _hasResults = true;
        });

        _fadeController.forward(from: 0);
        _showSnackBar('Analysis completed successfully', isError: false);
      } else {
        throw Exception('Analysis failed: ${response.statusCode}');
      }
    } catch (e) {
      _showSnackBar('Analysis failed: $e', isError: true);
    } finally {
      setState(() {
        _isProcessing = false;
      });
    }
  }

  void _startFactRotation() {
    Future.doWhile(() async {
      await Future.delayed(const Duration(seconds: 3));
      if (!_isProcessing) return false;

      if (mounted) {
        setState(() {
          _currentFactIndex = (_currentFactIndex + 1) % _medicalFacts.length;
        });
      }
      return _isProcessing;
    });
  }

  Future<void> _saveToDigitalTwin() async {
    if (!_hasResults) return;

    final user = FirebaseAuth.instance.currentUser;
    if (user == null) return;

    try {
      // Save directly to Firestore to avoid new backend endpoints
      final doc = {
        'filename': _selectedFileName,
        'confidence_score': _confidenceScore,
        'severity': _severity,
        'priority': _priority,
        'full_analysis': _fullAnalysis,
        'primary_analysis': _primaryAnalysis,
        'medical_inferences': _medicalInferences,
        'proactive_recommendations': _proactiveRecommendations,
        'timestamp': DateTime.now(),
        'analysis_type': 'upload_analyze_structured',
      };

      await FirebaseFirestore.instance
          .collection('digital_twin_analyses')
          .doc(user.uid)
          .collection('reports')
          .add(doc);

      _showSnackBar('Analysis saved to your Digital Twin memory',
          isError: false);
    } catch (e) {
      _showSnackBar('Failed to save: $e', isError: true);
    }
  }

  void _showSnackBar(String message, {required bool isError}) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: isError ? Colors.red : Colors.green,
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  // Lightweight parser to structure Gemini free text into UI sections
  Map<String, dynamic> _parseGeminiText(String text) {
    String lower = text.toLowerCase();

    int confidence = 75;
    final percent = RegExp(r"(\d{1,3})%\s*confidence|confidence\s*(\d{1,3})%|")
        .firstMatch(lower);
    if (percent != null) {
      final grp = percent.group(1) ?? percent.group(2);
      if (grp != null) {
        confidence = int.tryParse(grp) ?? confidence;
      }
    }

    String severity = 'Moderate';
    if (lower.contains('critical'))
      severity = 'Critical';
    else if (lower.contains('concerning') || lower.contains('worry'))
      severity = 'Concerning';
    else if (lower.contains('excellent') || lower.contains('optimal'))
      severity = 'Excellent';
    else if (lower.contains('good') || lower.contains('normal'))
      severity = 'Good';

    String priority = 'Medium';
    if (lower.contains('urgent') || lower.contains('immediate'))
      priority = 'Urgent';
    else if (lower.contains('high priority') || lower.contains('soon'))
      priority = 'High';
    else if (lower.contains('low priority') || lower.contains('routine'))
      priority = 'Low';

    String extractBetween(String start, String end) {
      final sIdx = text.indexOf(start);
      if (sIdx == -1) return '';
      final eIdx = end.isEmpty ? -1 : text.indexOf(end, sIdx + start.length);
      if (eIdx == -1) return text.substring(sIdx).trim();
      return text.substring(sIdx, eIdx).trim();
    }

    final primary = extractBetween('PRIMARY ANALYSIS', 'CONFIDENCE');
    final inferences = extractBetween('MEDICAL INFERENCES', 'PROACTIVE');
    final proactive = extractBetween('PROACTIVE RECOMMENDATIONS', 'SEVERITY');

    return {
      'confidence_score': confidence,
      'severity': severity,
      'priority': priority,
      'primary_analysis': primary.isNotEmpty ? primary : text,
      'medical_inferences': inferences,
      'proactive_recommendations': proactive,
      'full_analysis': text,
    };
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0A0E27),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _buildHeader(),
              const SizedBox(height: 32),
              _buildFileUploadSection(),
              const SizedBox(height: 24),
              _buildActionButtons(),
              const SizedBox(height: 32),
              if (_isProcessing) _buildProcessingSection(),
              if (_hasResults && !_isProcessing) _buildResultsSection(),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Digital Twin',
          style: TextStyle(
            fontSize: 36,
            fontWeight: FontWeight.bold,
            color: Colors.white,
            letterSpacing: -0.5,
          ),
        ),
        const SizedBox(height: 8),
        Text(
          'Upload Lab Test Report',
          style: TextStyle(
            fontSize: 18,
            color: Colors.white.withOpacity(0.6),
            fontWeight: FontWeight.w400,
          ),
        ),
      ],
    );
  }

  Widget _buildFileUploadSection() {
    return GestureDetector(
      onTap: _isProcessing ? null : _pickFile,
      child: Container(
        padding: const EdgeInsets.all(24),
        decoration: BoxDecoration(
          color: const Color(0xFF1A1F3A),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: Colors.blue.withOpacity(0.3),
            width: 2,
          ),
        ),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.blue.withOpacity(0.1),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Icon(
                Icons.upload_file,
                color: Colors.blue,
                size: 32,
              ),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    _selectedFileName ?? 'Choose File',
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                      color: Colors.white,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    _selectedFileName == null
                        ? 'PDF, TXT, DOC, or Image'
                        : 'File selected',
                    style: TextStyle(
                      fontSize: 14,
                      color: Colors.white.withOpacity(0.5),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildActionButtons() {
    return Row(
      children: [
        Expanded(
          child: ElevatedButton(
            onPressed: _isProcessing || _selectedFile == null
                ? null
                : _analyzeLabReport,
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.blue,
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(vertical: 16),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
              elevation: 0,
            ),
            child: Text(
              'Analyze Report',
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ),
        const SizedBox(width: 16),
        Expanded(
          child: ElevatedButton(
            onPressed:
                _hasResults && !_isProcessing ? _saveToDigitalTwin : null,
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF1A1F3A),
              foregroundColor: Colors.blue,
              padding: const EdgeInsets.symmetric(vertical: 16),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
                side: BorderSide(color: Colors.blue.withOpacity(0.5)),
              ),
              elevation: 0,
            ),
            child: Text(
              'Save Digital Twin',
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildProcessingSection() {
    return Container(
      padding: const EdgeInsets.all(32),
      decoration: BoxDecoration(
        color: const Color(0xFF1A1F3A),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        children: [
          // Lottie animation
          SizedBox(
            height: 200,
            child: Lottie.asset(
              'assets/animations/medical_scan.json',
              fit: BoxFit.contain,
              errorBuilder: (context, error, stackTrace) {
                // Fallback to circular progress indicator
                return const Center(
                  child: CircularProgressIndicator(
                    color: Colors.blue,
                    strokeWidth: 3,
                  ),
                );
              },
            ),
          ),
          const SizedBox(height: 24),
          Text(
            _medicalFacts[_currentFactIndex],
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: 16,
              color: Colors.white.withOpacity(0.8),
              fontWeight: FontWeight.w500,
            ),
          ),
          const SizedBox(height: 16),
          LinearProgressIndicator(
            backgroundColor: Colors.white.withOpacity(0.1),
            valueColor: AlwaysStoppedAnimation<Color>(Colors.blue),
          ),
        ],
      ),
    );
  }

  Widget _buildResultsSection() {
    return FadeTransition(
      opacity: _fadeAnimation,
      child: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [
              const Color(0xFF1A1F3A),
              const Color(0xFF0A0E27),
            ],
          ),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: _getSeverityColor(_severity).withOpacity(0.3),
            width: 2,
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header with metrics
            Container(
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                color: _getSeverityColor(_severity).withOpacity(0.1),
                borderRadius: const BorderRadius.only(
                  topLeft: Radius.circular(14),
                  topRight: Radius.circular(14),
                ),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Results',
                    style: TextStyle(
                      fontSize: 28,
                      fontWeight: FontWeight.bold,
                      color: Colors.white,
                    ),
                  ),
                  const SizedBox(height: 16),
                  Row(
                    children: [
                      _buildMetricChip(
                          'Confidence', '$_confidenceScore%', Colors.blue),
                      const SizedBox(width: 12),
                      _buildMetricChip('Severity', _severity ?? 'N/A',
                          _getSeverityColor(_severity)),
                      const SizedBox(width: 12),
                      _buildMetricChip('Priority', _priority ?? 'N/A',
                          _getPriorityColor(_priority)),
                    ],
                  ),
                ],
              ),
            ),

            // 3D Body Visualization + Analysis
            Padding(
              padding: const EdgeInsets.all(24),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // 3D Body (placeholder for now)
                  Expanded(
                    flex: 2,
                    child: Container(
                      height: 400,
                      decoration: BoxDecoration(
                        color: Colors.black.withOpacity(0.3),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: _build3DBodyVisualization(),
                    ),
                  ),
                  const SizedBox(width: 24),

                  // Analysis Text
                  Expanded(
                    flex: 3,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        _buildAnalysisSection(
                          'The digital twin suggests:',
                          _primaryAnalysis ?? '',
                        ),
                        const SizedBox(height: 16),
                        if (_medicalInferences != null &&
                            _medicalInferences!.isNotEmpty)
                          _buildAnalysisSection(
                            'Medical Inferences:',
                            _medicalInferences!,
                          ),
                        const SizedBox(height: 16),
                        if (_proactiveRecommendations != null &&
                            _proactiveRecommendations!.isNotEmpty)
                          _buildAnalysisSection(
                            'Proactive Recommendations:',
                            _proactiveRecommendations!,
                          ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMetricChip(String label, String value, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      decoration: BoxDecoration(
        color: color.withOpacity(0.2),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withOpacity(0.5)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            label,
            style: TextStyle(
              fontSize: 12,
              color: Colors.white.withOpacity(0.7),
            ),
          ),
          const SizedBox(width: 8),
          Text(
            value,
            style: TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.bold,
              color: color,
            ),
          ),
        ],
      ),
    );
  }

  Widget _build3DBodyVisualization() {
    // This will render the 3D human body with highlighted organs
    // For now, using a placeholder image
    return Stack(
      alignment: Alignment.center,
      children: [
        // Gradient background
        Container(
          decoration: BoxDecoration(
            gradient: RadialGradient(
              colors: [
                Colors.blue.withOpacity(0.1),
                Colors.transparent,
              ],
            ),
          ),
        ),
        // Body icon/illustration
        Icon(
          Icons.person,
          size: 200,
          color: Colors.blue.withOpacity(0.3),
        ),
        // Highlight effect for affected organs
        Positioned(
          top: 100,
          child: Container(
            width: 80,
            height: 80,
            decoration: BoxDecoration(
              color: Colors.red.withOpacity(0.3),
              shape: BoxShape.circle,
              boxShadow: [
                BoxShadow(
                  color: Colors.red.withOpacity(0.5),
                  blurRadius: 20,
                  spreadRadius: 10,
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildAnalysisSection(String title, String content) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.bold,
            color: Colors.white,
          ),
        ),
        const SizedBox(height: 8),
        Text(
          content,
          style: TextStyle(
            fontSize: 14,
            color: Colors.white.withOpacity(0.8),
            height: 1.5,
          ),
        ),
      ],
    );
  }

  Color _getSeverityColor(String? severity) {
    switch (severity?.toLowerCase()) {
      case 'critical':
        return Colors.red;
      case 'concerning':
        return Colors.orange;
      case 'moderate':
        return Colors.yellow;
      case 'good':
        return Colors.green;
      case 'excellent':
        return Colors.blue;
      default:
        return Colors.grey;
    }
  }

  Color _getPriorityColor(String? priority) {
    switch (priority?.toLowerCase()) {
      case 'urgent':
        return Colors.red;
      case 'high':
        return Colors.orange;
      case 'medium':
        return Colors.yellow;
      case 'low':
        return Colors.green;
      default:
        return Colors.grey;
    }
  }
}
