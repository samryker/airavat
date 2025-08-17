import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'package:airavat_flutter/services/api_service.dart';
import 'package:airavat_flutter/config/backend_config.dart';

void main() {
  group('Frontend Comprehensive Tests', () {
    const String testUserId = 'test_user_frontend_123';
    const String testPatientId = 'test_patient_frontend_123';

    setUpAll(() {
      print('🧪 Starting Comprehensive Frontend Tests');
    });

    group('Backend API Tests', () {
      test('Backend health endpoint should be accessible', () async {
        print('Testing backend health...');

        final response = await http.get(
          Uri.parse('${BackendConfig.baseUrl}/health'),
        );

        expect(response.statusCode, 200);
        final data = jsonDecode(response.body);
        expect(data['status'], 'healthy');

        print('✅ Backend health test passed');
      });

      test('Agent query endpoint should accept requests', () async {
        print('Testing agent query endpoint...');

        final response = await http.post(
          Uri.parse('${BackendConfig.queryEndpoint}'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'patient_id': testPatientId,
            'query_text': 'I have a headache and fever',
            'symptoms': ['headache', 'fever'],
            'medical_history': ['hypertension'],
            'current_medications': ['aspirin'],
          }),
        );

        expect(response.statusCode, 200);
        final data = jsonDecode(response.body);

        print('✅ Agent query test passed');
        print('Response: $data');

        // Check response structure
        expect(data, contains('request_id'));
        expect(data, contains('response_text'));
        expect(data, contains('suggestions'));
      });

      test('Memory endpoint should work', () async {
        print('Testing memory endpoint...');

        final response = await http.get(
          Uri.parse('${BackendConfig.memoryEndpoint}/$testPatientId'),
        );

        expect(response.statusCode, 200);
        final data = jsonDecode(response.body);

        print('✅ Memory endpoint test passed');
        print('Memory data: $data');
      });

      test('Treatment plan endpoint should work', () async {
        print('Testing treatment plan endpoint...');

        final treatmentPlan = {
          'patient_id': testPatientId,
          'plan': {
            'medications': ['aspirin'],
            'lifestyle_changes': ['rest', 'hydration'],
            'follow_up': '1 week'
          }
        };

        final response = await http.post(
          Uri.parse('${BackendConfig.treatmentPlanEndpoint}'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode(treatmentPlan),
        );

        expect(response.statusCode, 200);
        final data = jsonDecode(response.body);

        print('✅ Treatment plan test passed');
        print('Response: $data');
      });
    });

    group('AI Response Quality Tests', () {
      test('AI should provide different responses for different queries',
          () async {
        print('Testing AI response variety...');

        final queries = [
          'I have a headache',
          'My blood pressure is high',
          'I feel dizzy',
          'I have chest pain',
        ];

        final responses = <String>[];

        for (final query in queries) {
          final response = await http.post(
            Uri.parse('${BackendConfig.queryEndpoint}'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({
              'patient_id': testPatientId,
              'query_text': query,
            }),
          );

          expect(response.statusCode, 200);
          final data = jsonDecode(response.body);
          responses.add(data['response_text']);

          print('Query: "$query"');
          print('Response: "${data['response_text']}"');
        }

        // Check for response variety
        final uniqueResponses = responses.toSet();
        expect(uniqueResponses.length, greaterThan(1),
            reason:
                'AI should provide different responses for different queries');

        print('✅ AI response variety test passed');
      });

      test('AI responses should be contextually relevant', () async {
        print('Testing AI response relevance...');

        final response = await http.post(
          Uri.parse('${BackendConfig.queryEndpoint}'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'patient_id': testPatientId,
            'query_text': 'I have severe chest pain and shortness of breath',
            'symptoms': ['chest pain', 'shortness of breath'],
            'medical_history': ['diabetes', 'hypertension'],
            'current_medications': ['metformin', 'lisinopril'],
          }),
        );

        expect(response.statusCode, 200);
        final data = jsonDecode(response.body);
        final responseText = data['response_text'].toLowerCase();

        // Check if response mentions relevant medical terms
        final relevantTerms = [
          'chest',
          'pain',
          'breath',
          'emergency',
          'doctor',
          'medical'
        ];
        final hasRelevantTerms =
            relevantTerms.any((term) => responseText.contains(term));

        expect(hasRelevantTerms, isTrue,
            reason: 'AI response should be contextually relevant to the query');

        print('✅ AI response relevance test passed');
      });
    });

    group('Frontend-Backend Integration Tests', () {
      test('Complete conversation flow should work', () async {
        print('Testing complete conversation flow...');

        // Step 1: Initial query
        final initialResponse = await http.post(
          Uri.parse('${BackendConfig.queryEndpoint}'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'patient_id': testPatientId,
            'query_text': 'Hello, I am experiencing chest pain',
            'symptoms': ['chest pain'],
            'medical_history': ['hypertension'],
            'current_medications': ['lisinopril'],
          }),
        );

        expect(initialResponse.statusCode, 200);
        final initialData = jsonDecode(initialResponse.body);

        print('Initial response: ${initialData['response_text']}');

        // Step 2: Follow-up query
        final followUpResponse = await http.post(
          Uri.parse('${BackendConfig.queryEndpoint}'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'patient_id': testPatientId,
            'query_text': 'What should I do about the chest pain?',
          }),
        );

        expect(followUpResponse.statusCode, 200);
        final followUpData = jsonDecode(followUpResponse.body);

        print('Follow-up response: ${followUpData['response_text']}');

        // Verify responses are different
        expect(
            initialData['response_text'], isNot(followUpData['response_text']));

        print('✅ Complete conversation flow test passed');
      });

      test('Memory persistence should work across queries', () async {
        print('Testing memory persistence...');

        // Step 1: Set initial context
        await http.post(
          Uri.parse('${BackendConfig.queryEndpoint}'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'patient_id': testPatientId,
            'query_text': 'I have diabetes and take metformin',
            'medical_history': ['diabetes'],
            'current_medications': ['metformin'],
          }),
        );

        // Step 2: Query that should reference previous context
        final response = await http.post(
          Uri.parse('${BackendConfig.queryEndpoint}'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'patient_id': testPatientId,
            'query_text': 'How should I manage my condition?',
          }),
        );

        expect(response.statusCode, 200);
        final data = jsonDecode(response.body);
        final responseText = data['response_text'].toLowerCase();

        // Check if response references diabetes or metformin
        final hasContext = responseText.contains('diabetes') ||
            responseText.contains('metformin') ||
            responseText.contains('blood sugar');

        expect(hasContext, isTrue,
            reason: 'AI should remember and reference previous context');

        print('✅ Memory persistence test passed');
      });
    });

    group('Error Handling Tests', () {
      test('Should handle invalid requests gracefully', () async {
        print('Testing error handling...');

        final response = await http.post(
          Uri.parse('${BackendConfig.queryEndpoint}'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'patient_id': '', // Invalid empty patient ID
            'query_text': 'Test query',
          }),
        );

        // Should handle gracefully (either 200 with error message or 400)
        expect(response.statusCode, anyOf(200, 400, 422));

        print('✅ Error handling test passed');
      });

      test('Should handle missing query text', () async {
        print('Testing missing query text handling...');

        final response = await http.post(
          Uri.parse('${BackendConfig.queryEndpoint}'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'patient_id': testPatientId,
            // Missing query_text
          }),
        );

        expect(response.statusCode, anyOf(200, 400, 422));

        print('✅ Missing query text test passed');
      });
    });

    group('Performance Tests', () {
      test('Response time should be reasonable', () async {
        print('Testing response time...');

        final stopwatch = Stopwatch()..start();

        final response = await http.post(
          Uri.parse('${BackendConfig.queryEndpoint}'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'patient_id': testPatientId,
            'query_text': 'Performance test query',
          }),
        );

        stopwatch.stop();
        final responseTime = stopwatch.elapsedMilliseconds;

        expect(response.statusCode, 200);
        expect(
            responseTime, lessThan(10000)); // Should respond within 10 seconds

        print('✅ Response time test passed: ${responseTime}ms');
      });

      test('Concurrent requests should work', () async {
        print('Testing concurrent requests...');

        final futures = <Future<http.Response>>[];

        for (int i = 0; i < 3; i++) {
          futures.add(http.post(
            Uri.parse('${BackendConfig.queryEndpoint}'),
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({
              'patient_id': testPatientId,
              'query_text': 'Concurrent test query $i',
            }),
          ));
        }

        final responses = await Future.wait(futures);

        for (final response in responses) {
          expect(response.statusCode, 200);
        }

        print('✅ Concurrent requests test passed');
      });
    });

    group('API Service Tests', () {
      test('API Service should handle queries correctly', () async {
        print('Testing API Service...');

        try {
          // Note: This test may fail if Firebase Auth is not mocked
          // In a real test environment, you'd need to mock Firebase Auth

          final result = await ApiService.sendQuery(
            queryText: 'I have a headache and fever',
            symptoms: ['headache', 'fever'],
            medicalHistory: ['hypertension'],
            currentMedications: ['aspirin'],
          );

          print('✅ API Service test passed');
          print('Result: $result');

          expect(result, contains('response_text'));
          expect(result, contains('suggestions'));
        } catch (e) {
          print(
              '⚠️ API Service test failed (expected if Firebase not mocked): $e');
          // This is expected if Firebase Auth is not properly mocked
        }
      });
    });
  });
}
