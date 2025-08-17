import 'package:flutter/material.dart';
import '../services/context_retrieval_service.dart';

class ContextHistoryWidget extends StatefulWidget {
  final String patientId;
  final Function(String) onContextLoaded;

  const ContextHistoryWidget({
    Key? key,
    required this.patientId,
    required this.onContextLoaded,
  }) : super(key: key);

  @override
  State<ContextHistoryWidget> createState() => _ContextHistoryWidgetState();
}

class _ContextHistoryWidgetState extends State<ContextHistoryWidget> {
  PatientContext? _patientContext;
  bool _isLoading = false;
  bool _isExpanded = false;

  @override
  void initState() {
    super.initState();
    _loadPatientContext();
  }

  Future<void> _loadPatientContext() async {
    setState(() {
      _isLoading = true;
    });

    try {
      final context = await ContextRetrievalService()
          .retrievePatientContext(widget.patientId);

      if (mounted) {
        setState(() {
          _patientContext = context;
          _isLoading = false;
        });

        // Notify parent that context is loaded
        if (context != null) {
          widget.onContextLoaded(context.summaryForAI);
        }
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return Card(
        margin: const EdgeInsets.all(8.0),
        child: Padding(
          padding: const EdgeInsets.all(16.0),
          child: Row(
            children: [
              const CircularProgressIndicator(),
              const SizedBox(width: 16),
              const Text('Loading your medical history...'),
            ],
          ),
        ),
      );
    }

    if (_patientContext == null) {
      return Card(
        margin: const EdgeInsets.all(8.0),
        child: Padding(
          padding: const EdgeInsets.all(16.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  const Icon(Icons.info_outline, color: Colors.orange),
                  const SizedBox(width: 8),
                  const Text(
                    'No Medical History Found',
                    style: TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 16,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              const Text(
                'Start a conversation to build your medical profile. The AI will remember your health information for future conversations.',
                style: TextStyle(color: Colors.grey),
              ),
            ],
          ),
        ),
      );
    }

    return Card(
      margin: const EdgeInsets.all(8.0),
      child: Column(
        children: [
          // Header
          InkWell(
            onTap: () {
              setState(() {
                _isExpanded = !_isExpanded;
              });
            },
            child: Padding(
              padding: const EdgeInsets.all(16.0),
              child: Row(
                children: [
                  const Icon(Icons.medical_services, color: Colors.blue),
                  const SizedBox(width: 8),
                  const Text(
                    'Your Medical Profile',
                    style: TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 16,
                    ),
                  ),
                  const Spacer(),
                  Icon(
                    _isExpanded ? Icons.expand_less : Icons.expand_more,
                    color: Colors.grey,
                  ),
                ],
              ),
            ),
          ),

          // Content
          if (_isExpanded)
            Padding(
              padding: const EdgeInsets.fromLTRB(16.0, 0, 16.0, 16.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Divider(),
                  const SizedBox(height: 8),

                  // Profile section
                  if (_patientContext!.profile.isNotEmpty) ...[
                    _buildSection(
                      'Patient Profile',
                      Icons.person,
                      [
                        if (_patientContext!.profile['age'] != null)
                          'Age: ${_patientContext!.profile['age']}',
                        if (_patientContext!.profile['gender'] != null)
                          'Gender: ${_patientContext!.profile['gender']}',
                        if (_patientContext!.profile['bmi_index'] != null)
                          'BMI: ${_patientContext!.profile['bmi_index']}',
                        if (_patientContext!.profile['goal'] != null)
                          'Health Goal: ${_patientContext!.profile['goal']}',
                      ],
                    ),
                  ],

                  // Medical history
                  if (_patientContext!.profile['history'] != null &&
                      (_patientContext!.profile['history'] as List)
                          .isNotEmpty) ...[
                    _buildSection(
                      'Medical History',
                      Icons.medical_services,
                      (_patientContext!.profile['history'] as List)
                          .cast<String>(),
                    ),
                  ],

                  // Medications
                  if (_patientContext!.profile['medicines'] != null &&
                      (_patientContext!.profile['medicines'] as List)
                          .isNotEmpty) ...[
                    _buildSection(
                      'Current Medications',
                      Icons.medication,
                      (_patientContext!.profile['medicines'] as List)
                          .cast<String>(),
                    ),
                  ],

                  // Allergies
                  if (_patientContext!.profile['allergies'] != null &&
                      (_patientContext!.profile['allergies'] as List)
                          .isNotEmpty) ...[
                    _buildSection(
                      'Allergies',
                      Icons.warning,
                      (_patientContext!.profile['allergies'] as List)
                          .cast<String>(),
                    ),
                  ],

                  // Treatment plans
                  if (_patientContext!.treatmentPlans.isNotEmpty) ...[
                    _buildSection(
                      'Treatment Plans',
                      Icons.assignment,
                      _patientContext!.treatmentPlans.map((plan) {
                        final parts = <String>[];
                        if (plan['medications'] != null) {
                          parts.add(
                              'Medications: ${(plan['medications'] as List).join(', ')}');
                        }
                        if (plan['lifestyle_changes'] != null) {
                          parts.add(
                              'Lifestyle: ${(plan['lifestyle_changes'] as List).join(', ')}');
                        }
                        if (plan['follow_up'] != null) {
                          parts.add('Follow-up: ${plan['follow_up']}');
                        }
                        return parts.join(' | ');
                      }).toList(),
                    ),
                  ],

                  // Biomarkers
                  if (_patientContext!.biomarkers.isNotEmpty) ...[
                    _buildSection(
                      'Recent Biomarkers',
                      Icons.analytics,
                      _patientContext!.biomarkers.entries
                          .map((e) => '${e.key}: ${e.value}')
                          .toList(),
                    ),
                  ],

                  const SizedBox(height: 16),

                  // Confirmation message
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: Colors.green.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: Colors.green.withOpacity(0.3)),
                    ),
                    child: Row(
                      children: [
                        const Icon(Icons.check_circle,
                            color: Colors.green, size: 20),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            'Your medical history is loaded and will be used to provide personalized responses.',
                            style: TextStyle(
                              color: Colors.green[700],
                              fontSize: 12,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildSection(String title, IconData icon, List<String> items) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, color: Colors.blue, size: 18),
              const SizedBox(width: 8),
              Text(
                title,
                style: const TextStyle(
                  fontWeight: FontWeight.bold,
                  fontSize: 14,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          ...items.map((item) => Padding(
                padding: const EdgeInsets.only(left: 26.0, bottom: 4.0),
                child: Text(
                  '• $item',
                  style: const TextStyle(fontSize: 13),
                ),
              )),
        ],
      ),
    );
  }
}
