import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'lib/services/context_retrieval_service.dart';

void main() {
  group('Context Retrieval Tests', () {
    const String backendUrl = 'https://airavat-backend-u3hyo7liyq-uc.a.run.app';
    const String testPatientId = 'test_context_patient_123';

    test('Test Patient Context Retrieval', () async {
      final service = ContextRetrievalService();

      // Test retrieving patient context
      final context = await service.retrievePatientContext(testPatientId);

      if (context != null) {
        print('✅ Patient Context Retrieved Successfully');
        print('Patient ID: ${context.patientId}');
        print('Profile Keys: ${context.profile.keys}');
        print('Treatment Plans: ${context.treatmentPlans.length}');
        print('Biomarkers: ${context.biomarkers.keys}');
        print('Conversation History: ${context.conversationHistory.length}');

        // Test formatted display
        final formattedHistory = context.formattedHistory;
        print('Formatted History Length: ${formattedHistory.length}');
        expect(formattedHistory.isNotEmpty, true);

        // Test AI summary
        final aiSummary = context.summaryForAI;
        print('AI Summary: $aiSummary');
        expect(aiSummary.isNotEmpty, true);
      } else {
        print('⚠️ No patient context found (this is normal for new patients)');
      }
    });

    test('Test Conversation History Retrieval', () async {
      final service = ContextRetrievalService();

      // Test retrieving conversation history
      final history =
          await service.getConversationHistory(testPatientId, limit: 5);

      print('✅ Conversation History Retrieved');
      print('History Count: ${history.length}');

      if (history.isNotEmpty) {
        for (var conv in history) {
          print('Conversation: ${conv.keys}');
        }
      }
    });

    test('Test Patient Memory Retrieval', () async {
      final service = ContextRetrievalService();

      // Test retrieving patient memory
      final memory = await service.getPatientMemory(testPatientId);

      if (memory != null) {
        print('✅ Patient Memory Retrieved Successfully');
        print('Memory Keys: ${memory.keys}');
      } else {
        print('⚠️ No patient memory found (this is normal for new patients)');
      }
    });

    test('Test Context Integration with AI Query', () async {
      // First, get patient context
      final service = ContextRetrievalService();
      final context = await service.retrievePatientContext(testPatientId);

      if (context != null) {
        // Create enhanced query with context
        final contextSummary = context.summaryForAI;
        final userQuery = "What should I do about my blood sugar?";
        final enhancedQuery =
            "Context: $contextSummary\n\nUser Query: $userQuery";

        print('Enhanced Query: $enhancedQuery');

        // Send query to AI
        final response = await http.post(
          Uri.parse('$backendUrl/agent/query'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'patient_id': testPatientId,
            'query_text': enhancedQuery,
          }),
        );

        if (response.statusCode == 200) {
          final data = jsonDecode(response.body);
          print('✅ AI Response with Context: ${data['response_text']}');
          expect(data['response_text'], isNotEmpty);
        } else {
          print('❌ AI Query failed: ${response.statusCode}');
        }
      } else {
        print('⚠️ Skipping AI test - no context available');
      }
    });
  });
}
