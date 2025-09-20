import 'package:flutter/material.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:file_picker/file_picker.dart';
import 'dart:convert';
import '../services/digital_twin_service.dart';

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
    final result = await FilePicker.platform.pickFiles(type: FileType.any);
    if (result != null && result.files.single.bytes != null) {
      try {
        final content = utf8.decode(result.files.single.bytes!);
        final data = jsonDecode(content);
        final map = <String, double>{};
        (data as Map).forEach((k, v) {
          final numVal = (v as num?)?.toDouble();
          if (numVal != null) map[k.toString()] = numVal;
        });
        setState(() => _biomarkers = map);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Imported ${map.length} biomarkers')),
        );
      } catch (e) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Invalid JSON file: $e')),
        );
      }
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
                  label: const Text('Import Biomarkers (JSON)'),
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
              child: Row(
                children: [
                  Expanded(
                    child: Card(
                      child: Padding(
                        padding: const EdgeInsets.all(12.0),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text('Current Twin'),
                            const SizedBox(height: 8),
                            Expanded(
                              child: SingleChildScrollView(
                                child: Text(
                                  jsonEncode({
                                    'patient_id': _currentTwin?.patientId,
                                    'height_cm': _currentTwin?.heightCm,
                                    'weight_kg': _currentTwin?.weightKg,
                                    'biomarkers': _currentTwin?.biomarkers,
                                    'updated_at': _currentTwin?.updatedAt,
                                  }),
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Card(
                      child: Padding(
                        padding: const EdgeInsets.all(12.0),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text('AI Inference'),
                            const SizedBox(height: 8),
                            Expanded(
                              child: SingleChildScrollView(
                                child: Text(_inference ?? 'No inference yet'),
                              ),
                            ),
                          ],
                        ),
                      ),
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
}
