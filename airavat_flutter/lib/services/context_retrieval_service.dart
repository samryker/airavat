import 'dart:convert';
import 'package:http/http.dart' as http;
import '../config/backend_config.dart';

class PatientContext {
  final String patientId;
  final Map<String, dynamic> profile;
  final List<Map<String, dynamic>> treatmentPlans;
  final Map<String, dynamic> biomarkers;
  final List<Map<String, dynamic>> conversationHistory;
  final Map<String, dynamic> mcpMemory;
  final DateTime lastUpdated;

  PatientContext({
    required this.patientId,
    required this.profile,
    required this.treatmentPlans,
    required this.biomarkers,
    required this.conversationHistory,
    required this.mcpMemory,
    required this.lastUpdated,
  });

  factory PatientContext.fromJson(Map<String, dynamic> json) {
    return PatientContext(
      patientId: json['patient_id'] ?? '',
      profile: json['profile'] ?? {},
      treatmentPlans:
          List<Map<String, dynamic>>.from(json['treatment_plans'] ?? []),
      biomarkers: json['biomarkers'] ?? {},
      conversationHistory:
          List<Map<String, dynamic>>.from(json['conversation_history'] ?? []),
      mcpMemory: json['mcp_memory'] ?? {},
      lastUpdated:
          DateTime.tryParse(json['last_updated'] ?? '') ?? DateTime.now(),
    );
  }

  String get formattedHistory {
    final buffer = StringBuffer();

    // Profile information
    if (profile.isNotEmpty) {
      buffer.writeln('📋 **Patient Profile:**');
      if (profile['age'] != null) buffer.writeln('• Age: ${profile['age']}');
      if (profile['gender'] != null)
        buffer.writeln('• Gender: ${profile['gender']}');
      if (profile['bmi_index'] != null)
        buffer.writeln('• BMI: ${profile['bmi_index']}');
      if (profile['race'] != null) buffer.writeln('• Race: ${profile['race']}');
      if (profile['goal'] != null)
        buffer.writeln('• Health Goal: ${profile['goal']}');
      buffer.writeln('');
    }

    // Medical history
    if (profile['history'] != null && (profile['history'] as List).isNotEmpty) {
      buffer.writeln('🏥 **Medical History:**');
      for (var condition in profile['history']) {
        buffer.writeln('• $condition');
      }
      buffer.writeln('');
    }

    // Current medications
    if (profile['medicines'] != null &&
        (profile['medicines'] as List).isNotEmpty) {
      buffer.writeln('💊 **Current Medications:**');
      for (var medicine in profile['medicines']) {
        buffer.writeln('• $medicine');
      }
      buffer.writeln('');
    }

    // Allergies
    if (profile['allergies'] != null &&
        (profile['allergies'] as List).isNotEmpty) {
      buffer.writeln('⚠️ **Allergies:**');
      for (var allergy in profile['allergies']) {
        buffer.writeln('• $allergy');
      }
      buffer.writeln('');
    }

    // Treatment plans
    if (treatmentPlans.isNotEmpty) {
      buffer.writeln('📋 **Treatment Plans:**');
      for (var plan in treatmentPlans) {
        if (plan['medications'] != null) {
          buffer.writeln(
              '• Medications: ${(plan['medications'] as List).join(', ')}');
        }
        if (plan['lifestyle_changes'] != null) {
          buffer.writeln(
              '• Lifestyle: ${(plan['lifestyle_changes'] as List).join(', ')}');
        }
        if (plan['follow_up'] != null) {
          buffer.writeln('• Follow-up: ${plan['follow_up']}');
        }
        buffer.writeln('');
      }
    }

    // Biomarkers
    if (biomarkers.isNotEmpty) {
      buffer.writeln('📊 **Recent Biomarkers:**');
      biomarkers.forEach((key, value) {
        buffer.writeln('• $key: $value');
      });
      buffer.writeln('');
    }

    // Recent conversation history
    if (conversationHistory.isNotEmpty) {
      buffer.writeln('💬 **Recent Conversations:**');
      final recentConversations = conversationHistory.take(3).toList();
      for (var conv in recentConversations) {
        if (conv['query_text'] != null) {
          buffer.writeln('• Q: ${conv['query_text']}');
        }
        if (conv['response_text'] != null) {
          buffer.writeln(
              '  A: ${(conv['response_text'] as String).substring(0, 50)}...');
        }
        buffer.writeln('');
      }
    }

    return buffer.toString();
  }

  String get summaryForAI {
    final buffer = StringBuffer();

    // Essential context for AI
    if (profile.isNotEmpty) {
      if (profile['age'] != null) buffer.write('Age: ${profile['age']}, ');
      if (profile['gender'] != null)
        buffer.write('Gender: ${profile['gender']}, ');
      if (profile['history'] != null &&
          (profile['history'] as List).isNotEmpty) {
        buffer.write(
            'Medical History: ${(profile['history'] as List).join(', ')}, ');
      }
      if (profile['medicines'] != null &&
          (profile['medicines'] as List).isNotEmpty) {
        buffer.write(
            'Current Medications: ${(profile['medicines'] as List).join(', ')}, ');
      }
      if (profile['allergies'] != null &&
          (profile['allergies'] as List).isNotEmpty) {
        buffer
            .write('Allergies: ${(profile['allergies'] as List).join(', ')}, ');
      }
    }

    if (biomarkers.isNotEmpty) {
      buffer.write(
          'Recent Biomarkers: ${biomarkers.entries.map((e) => '${e.key}: ${e.value}').join(', ')}, ');
    }

    return buffer.toString();
  }
}

class ContextRetrievalService {
  static final ContextRetrievalService _instance =
      ContextRetrievalService._internal();
  factory ContextRetrievalService() => _instance;
  ContextRetrievalService._internal();

  Future<PatientContext?> retrievePatientContext(String patientId) async {
    try {
      // Get complete patient context from backend
      final response = await http.get(
        Uri.parse('${BackendConfig.baseUrl}/agent/patient/$patientId/context'),
        headers: {'Content-Type': 'application/json'},
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['status'] == 'success' && data['context'] != null) {
          return PatientContext.fromJson(data['context']);
        }
      }

      // Fallback: Get memory data
      final memoryResponse = await http.get(
        Uri.parse('${BackendConfig.baseUrl}/agent/memory/$patientId'),
        headers: {'Content-Type': 'application/json'},
      );

      if (memoryResponse.statusCode == 200) {
        final memoryData = jsonDecode(memoryResponse.body);
        if (memoryData['memory_data'] != null) {
          return PatientContext.fromJson(memoryData['memory_data']);
        }
      }

      return null;
    } catch (e) {
      print('Error retrieving patient context: $e');
      return null;
    }
  }

  Future<List<Map<String, dynamic>>> getConversationHistory(String patientId,
      {int limit = 10}) async {
    try {
      final response = await http.get(
        Uri.parse(
            '${BackendConfig.baseUrl}/agent/patient/$patientId/conversation-history?limit=$limit'),
        headers: {'Content-Type': 'application/json'},
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['status'] == 'success' &&
            data['conversation_history'] != null) {
          return List<Map<String, dynamic>>.from(data['conversation_history']);
        }
      }

      return [];
    } catch (e) {
      print('Error retrieving conversation history: $e');
      return [];
    }
  }

  Future<Map<String, dynamic>?> getPatientMemory(String patientId) async {
    try {
      final response = await http.get(
        Uri.parse('${BackendConfig.baseUrl}/agent/memory/$patientId'),
        headers: {'Content-Type': 'application/json'},
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return data['memory_data'];
      }

      return null;
    } catch (e) {
      print('Error retrieving patient memory: $e');
      return null;
    }
  }

  String formatContextForDisplay(PatientContext context) {
    return context.formattedHistory;
  }

  String formatContextForAI(PatientContext context) {
    return context.summaryForAI;
  }
}
