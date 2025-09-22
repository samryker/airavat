import 'package:flutter/material.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:file_picker/file_picker.dart';
import 'dart:convert';
import 'package:http/http.dart' as http;
import '../services/digital_twin_service.dart';
import '../services/api_service.dart';

class DigitalTwinScreen extends StatefulWidget {
  const DigitalTwinScreen({super.key});

  @override
  State<DigitalTwinScreen> createState() => _DigitalTwinScreenState();
}

class _DigitalTwinScreenState extends State<DigitalTwinScreen> {
  final _heightCtrl = TextEditingController(text: '170');
  final _weightCtrl = TextEditingController(text: '70');
  final _reportCtrl = TextEditingController();
  Map<String, double> _biomarkers = {
    'hemoglobin': 14.0,
    'glucose': 100.0,
  };

  bool _loading = false;
  String? _status;
  DigitalTwinRecord? _currentTwin;
  String? _inference;
  String? _medicalModelResponse;
  String? _geneticAnalysisResult;

  @override
  void dispose() {
    _heightCtrl.dispose();
    _weightCtrl.dispose();
    _reportCtrl.dispose();
    super.dispose();
  }

  Future<void> _fetchTwin() async {
    setState(() {
      _loading = true;
      _status = 'Fetching twin...';
    });
    try {
      final twin = await DigitalTwinService.getTwin();
      setState(() {
        _currentTwin = twin;
        _heightCtrl.text = twin.heightCm.toString();
        _weightCtrl.text = twin.weightKg.toString();
        _biomarkers = twin.biomarkers ?? {};
        _status = 'Twin loaded';
      });
    } catch (e) {
      setState(() {
        _status = 'Fetch failed: $e';
      });
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _upsertTwin() async {
    setState(() {
      _loading = true;
      _status = 'Saving twin...';
    });
    try {
      final payload = DigitalTwinPayload(
        heightCm: double.tryParse(_heightCtrl.text) ?? 170,
        weightKg: double.tryParse(_weightCtrl.text) ?? 70,
        biomarkers: _biomarkers,
      );
      final twin = await DigitalTwinService.upsertTwin(payload);
      setState(() {
        _currentTwin = twin;
        _status = 'Twin saved';
      });
    } catch (e) {
      setState(() => _status = 'Save failed: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _processTreatment() async {
    setState(() {
      _loading = true;
      _status = 'Processing treatment...';
    });
    try {
      // First update biomarkers in the live twin system
      if (_biomarkers.isNotEmpty) {
        await DigitalTwinService.updateBiomarkers(_biomarkers);
        print('✅ Biomarkers updated in live twin system');
      }

      // Then process treatment with updated data
      final payload = TreatmentUpdatePayload(
        report: _reportCtrl.text.trim().isEmpty
            ? 'General checkup report'
            : _reportCtrl.text.trim(),
        heightCm: double.tryParse(_heightCtrl.text) ?? 170,
        weightKg: double.tryParse(_weightCtrl.text) ?? 70,
        biomarkers: _biomarkers,
      );
      final resp = await DigitalTwinService.processTreatment(payload);

      // Get updated live twin data
      final liveTwinData = await DigitalTwinService.getLiveTwinData();
      print('📊 Live twin data: $liveTwinData');

      setState(() {
        _currentTwin = resp.twin;
        _inference = resp.inference;
        _status = 'Treatment processed with live biomarkers';
      });

      // Show enhanced result dialog with live data
      _showLiveResultDialog(resp, liveTwinData);
    } catch (e) {
      setState(() => _status = 'Process failed: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  void _showLiveResultDialog(
      TreatmentUpdateResponse result, Map<String, dynamic> liveTwinData) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('🧬 Live Digital Twin Update'),
        content: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text('✅ Treatment: ${result.inference}'),
              const SizedBox(height: 16),
              const Text('📊 Live Biomarkers:',
                  style: TextStyle(fontWeight: FontWeight.bold)),
              const SizedBox(height: 8),
              ...((liveTwinData['biomarkers'] as Map<String, dynamic>? ?? {})
                  .entries
                  .map((e) => Padding(
                        padding: const EdgeInsets.symmetric(vertical: 2),
                        child: Text('• ${e.key}: ${e.value}'),
                      ))),
              const SizedBox(height: 16),
              if (liveTwinData['ai_insights'] != null) ...[
                const Text('🤖 AI Insights:',
                    style: TextStyle(fontWeight: FontWeight.bold)),
                const SizedBox(height: 8),
                Text(liveTwinData['ai_insights'].toString()),
              ],
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }

  Future<void> _importBiomarkersFromFile() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['json', 'txt', 'csv', 'pdf', 'vcf', 'fasta', 'fastq'],
      allowMultiple: false,
    );

    if (result != null && result.files.single.bytes != null) {
      setState(() {
        _loading = true;
        _status = 'Processing file...';
      });

      try {
        final file = result.files.single;
        final userId = FirebaseAuth.instance.currentUser?.uid;

        if (userId == null) {
          throw Exception('User not authenticated');
        }

        // Try to import as JSON biomarkers first
        if (file.extension?.toLowerCase() == 'json') {
          try {
            final content = utf8.decode(file.bytes!);
            final data = jsonDecode(content);
            final map = <String, double>{};
            (data as Map).forEach((k, v) {
              final numVal = (v as num?)?.toDouble();
              if (numVal != null) map[k.toString()] = numVal;
            });
            setState(() => _biomarkers = map);

            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                  content: Text('Imported ${map.length} biomarkers from JSON')),
            );
          } catch (jsonError) {
            print(
                'Not a valid biomarker JSON, treating as genetic file: $jsonError');
          }
        }

        // Send to genetic analysis service for medical model analysis
        try {
          setState(() => _status = 'Analyzing with medical model...');

          // Upload to genetic analysis endpoint
          final geneticResponse =
              await _uploadToGeneticAnalysis(file.bytes!, file.name, userId);

          setState(() {
            _geneticAnalysisResult = geneticResponse['detailed_analysis'] ??
                geneticResponse['message'] ??
                'Genetic analysis completed';
            _status = 'File processed successfully';
          });

          // Also get medical model response via file analysis
          final medicalResponse = await ApiService.analyzeFile(
            fileBytes: file.bytes!,
            filename: file.name,
            contentType: _getContentType(file.name),
          );

          setState(() {
            _medicalModelResponse =
                medicalResponse['analysis'] ?? 'Medical analysis completed';
          });

          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
                content:
                    Text('File analyzed with both Gemini and Medical Model')),
          );
        } catch (analysisError) {
          print('Genetic/Medical analysis failed: $analysisError');
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Analysis failed: $analysisError')),
          );
        }
      } catch (e) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error processing file: $e')),
        );
      } finally {
        setState(() => _loading = false);
      }
    }
  }

  Future<Map<String, dynamic>> _uploadToGeneticAnalysis(
      List<int> fileBytes, String filename, String userId) async {
    try {
      final uri = Uri.parse(
          'https://airavat-backend-10892877764.us-central1.run.app/genetic/analyze');
      final request = http.MultipartRequest('POST', uri);

      request.files.add(http.MultipartFile.fromBytes(
        'file',
        fileBytes,
        filename: filename,
      ));

      request.fields['user_id'] = userId;
      request.fields['report_type'] = _detectReportType(filename);

      final streamedResponse = await request.send();
      final response = await http.Response.fromStream(streamedResponse);

      if (response.statusCode == 200) {
        final result = jsonDecode(response.body) as Map<String, dynamic>;

        // Format the response for display
        if (result['status'] == 'success' && result['analysis'] != null) {
          final analysis = result['analysis'] as Map<String, dynamic>;
          final summary = analysis['summary'] ?? 'Analysis completed';
          final markers = analysis['genetic_markers'] as List? ?? [];
          final genes = analysis['genes_analyzed'] as List? ?? [];

          return {
            'status': 'success',
            'message': summary,
            'detailed_analysis':
                'Found ${markers.length} genetic markers and ${genes.length} genes.\n\nMarkers: ${markers.map((m) => m['gene_name']).join(', ')}\n\nGenes: ${genes.join(', ')}',
            'file_type': result['file_type'],
            'processed_at': result['processed_at']
          };
        }

        return result;
      } else {
        throw Exception(
            'Genetic analysis failed: ${response.statusCode} - ${response.body}');
      }
    } catch (e) {
      throw Exception('Error uploading to genetic service: $e');
    }
  }

  String _detectReportType(String filename) {
    final extension = filename.toLowerCase().split('.').last;
    switch (extension) {
      case 'vcf':
        return 'vcf_file';
      case 'fasta':
      case 'fa':
        return 'fasta_file';
      case 'fastq':
      case 'fq':
        return 'fastq_file';
      case 'pdf':
        return 'lab_report';
      case 'json':
        return 'genetic_test';
      default:
        return 'unknown';
    }
  }

  String _getContentType(String fileName) {
    final extension = fileName.toLowerCase().split('.').last;
    switch (extension) {
      case 'pdf':
        return 'application/pdf';
      case 'json':
        return 'application/json';
      case 'csv':
        return 'text/csv';
      case 'txt':
        return 'text/plain';
      case 'vcf':
        return 'text/plain';
      case 'fasta':
      case 'fa':
        return 'text/plain';
      case 'fastq':
      case 'fq':
        return 'text/plain';
      default:
        return 'application/octet-stream';
    }
  }

  @override
  Widget build(BuildContext context) {
    final user = FirebaseAuth.instance.currentUser;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Digital Twin Service'),
      ),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (user != null) Text('User: ${user.uid}'),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _heightCtrl,
                    keyboardType: TextInputType.number,
                    decoration: const InputDecoration(
                      labelText: 'Height (cm)',
                      border: OutlineInputBorder(),
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: TextField(
                    controller: _weightCtrl,
                    keyboardType: TextInputType.number,
                    decoration: const InputDecoration(
                      labelText: 'Weight (kg)',
                      border: OutlineInputBorder(),
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                ElevatedButton.icon(
                  onPressed: _importBiomarkersFromFile,
                  icon: const Icon(Icons.upload_file),
                  label: const Text('Upload File (JSON/Genetic)'),
                ),
                const SizedBox(width: 12),
                ElevatedButton.icon(
                  onPressed: _fetchTwin,
                  icon: const Icon(Icons.download),
                  label: const Text('Fetch Saved Twin'),
                ),
                const SizedBox(width: 12),
                ElevatedButton.icon(
                  onPressed: _upsertTwin,
                  icon: const Icon(Icons.save),
                  label: const Text('Save/Update Twin'),
                ),
              ],
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _reportCtrl,
              maxLines: 3,
              decoration: const InputDecoration(
                labelText: 'Report (optional for treatment processing)',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 12),
            ElevatedButton.icon(
              onPressed: _processTreatment,
              icon: const Icon(Icons.medical_services_outlined),
              label: const Text('Process Treatment with AI'),
            ),
            const SizedBox(height: 12),
            if (_loading) const LinearProgressIndicator(),
            if (_status != null) Text(_status!),
            const SizedBox(height: 12),
            Expanded(
              child: LayoutBuilder(
                builder: (context, constraints) {
                  final isMobile = constraints.maxWidth < 768;

                  if (isMobile) {
                    // Mobile: Stack vertically
                    return SingleChildScrollView(
                      child: Column(
                        children: [
                          _buildTwinDataCard(),
                          const SizedBox(height: 12),
                          _buildDualAIResponseCards(),
                        ],
                      ),
                    );
                  } else {
                    // Desktop/Tablet: Three columns
                    return Row(
                      children: [
                        Expanded(flex: 1, child: _buildTwinDataCard()),
                        const SizedBox(width: 12),
                        Expanded(flex: 2, child: _buildDualAIResponseCards()),
                      ],
                    );
                  }
                },
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTwinDataCard() {
    return Card(
      elevation: 4,
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.person_outline,
                    color: Theme.of(context).primaryColor),
                const SizedBox(width: 8),
                const Text(
                  'Current Twin',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                ),
              ],
            ),
            const Divider(),
            Expanded(
              child: SingleChildScrollView(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (_currentTwin != null) ...[
                      _buildInfoRow('Patient ID', _currentTwin!.patientId),
                      _buildInfoRow('Height', '${_currentTwin!.heightCm} cm'),
                      _buildInfoRow('Weight', '${_currentTwin!.weightKg} kg'),
                      _buildInfoRow('BMI',
                          '${(_currentTwin!.weightKg / ((_currentTwin!.heightCm / 100) * (_currentTwin!.heightCm / 100))).toStringAsFixed(1)}'),
                      if (_currentTwin!.biomarkers != null &&
                          _currentTwin!.biomarkers!.isNotEmpty) ...[
                        const SizedBox(height: 12),
                        const Text('Biomarkers:',
                            style: TextStyle(fontWeight: FontWeight.w600)),
                        const SizedBox(height: 8),
                        ..._currentTwin!.biomarkers!.entries
                            .map((e) => _buildInfoRow(e.key, '${e.value}')),
                      ],
                      if (_currentTwin!.updatedAt != null) ...[
                        const SizedBox(height: 12),
                        _buildInfoRow('Updated', _currentTwin!.updatedAt!),
                      ],
                    ] else ...[
                      const Center(
                        child: Text(
                          'No twin data yet\nSave or fetch twin to see data',
                          textAlign: TextAlign.center,
                          style: TextStyle(color: Colors.grey),
                        ),
                      ),
                    ],
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildDualAIResponseCards() {
    return Column(
      children: [
        // Gemini AI Response
        Expanded(
          child: Card(
            elevation: 4,
            color: Colors.blue.shade50,
            child: Padding(
              padding: const EdgeInsets.all(16.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(Icons.psychology, color: Colors.blue.shade700),
                      const SizedBox(width: 8),
                      Text(
                        'Gemini AI Analysis',
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                          color: Colors.blue.shade700,
                        ),
                      ),
                    ],
                  ),
                  const Divider(),
                  Expanded(
                    child: SingleChildScrollView(
                      child: Text(
                        _inference ??
                            'No Gemini analysis yet\nProcess treatment to get AI insights',
                        style: TextStyle(
                          color:
                              _inference != null ? Colors.black87 : Colors.grey,
                          height: 1.4,
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
        const SizedBox(height: 12),
        // Medical Model Response
        Expanded(
          child: Card(
            elevation: 4,
            color: Colors.green.shade50,
            child: Padding(
              padding: const EdgeInsets.all(16.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(Icons.biotech, color: Colors.green.shade700),
                      const SizedBox(width: 8),
                      Text(
                        'Medical Model Analysis',
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                          color: Colors.green.shade700,
                        ),
                      ),
                    ],
                  ),
                  const Divider(),
                  Expanded(
                    child: SingleChildScrollView(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          if (_medicalModelResponse != null) ...[
                            const Text(
                              'File Analysis:',
                              style: TextStyle(fontWeight: FontWeight.w600),
                            ),
                            const SizedBox(height: 8),
                            Text(
                              _medicalModelResponse!,
                              style: const TextStyle(
                                  color: Colors.black87, height: 1.4),
                            ),
                          ],
                          if (_geneticAnalysisResult != null) ...[
                            const SizedBox(height: 16),
                            const Text(
                              'Genetic Analysis:',
                              style: TextStyle(fontWeight: FontWeight.w600),
                            ),
                            const SizedBox(height: 8),
                            Text(
                              _geneticAnalysisResult!,
                              style: const TextStyle(
                                  color: Colors.black87, height: 1.4),
                            ),
                          ],
                          if (_medicalModelResponse == null &&
                              _geneticAnalysisResult == null) ...[
                            const Text(
                              'No medical model analysis yet\nUpload files to get specialized medical insights',
                              style: TextStyle(color: Colors.grey, height: 1.4),
                            ),
                          ],
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildInfoRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4.0),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 80,
            child: Text(
              '$label:',
              style: const TextStyle(fontWeight: FontWeight.w600),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: const TextStyle(color: Colors.black87),
            ),
          ),
        ],
      ),
    );
  }
}
