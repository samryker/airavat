import 'dart:convert';
import 'package:http/http.dart' as http;

void main() async {
  print('🧪 Testing Airavat API Integration...\n');

  const String baseUrl =
      'https://airavat-fastapi-124145466298.us-central1.run.app';

  // Test 1: Basic API connectivity
  print('1️⃣ Testing basic API connectivity...');
  try {
    final response = await http.get(Uri.parse('$baseUrl/'));
    if (response.statusCode == 200) {
      print('✅ API is accessible');
      print('   Response: ${response.body}');
    } else {
      print('❌ API returned status code: ${response.statusCode}');
    }
  } catch (e) {
    print('❌ Failed to connect to API: $e');
  }

  print('\n2️⃣ Testing AI agent query...');
  try {
    final response = await http.post(
      Uri.parse('$baseUrl/agent/query'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'patient_id': 'test_user_123',
        'query_text': 'Hello, I have a question about my health.',
      }),
    );

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      print('✅ Query successful!');
      print('   Request ID: ${data['request_id']}');
      print('   Response: ${data['response_text'].substring(0, 100)}...');
      print('   Suggestions: ${data['suggestions']?.length ?? 0} suggestions');

      // Test 3: Feedback submission
      print('\n3️⃣ Testing feedback submission...');
      final feedbackResponse = await http.post(
        Uri.parse('$baseUrl/agent/feedback'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'request_id': data['request_id'],
          'patient_id': 'test_user_123',
          'outcome_works': true,
          'feedback_text': 'Great response!',
        }),
      );

      if (feedbackResponse.statusCode == 200) {
        final feedbackData = jsonDecode(feedbackResponse.body);
        print('✅ Feedback submitted successfully!');
        print('   Status: ${feedbackData['status']}');
      } else {
        print(
            '⚠️ Feedback submission returned status: ${feedbackResponse.statusCode}');
        print('   Response: ${feedbackResponse.body}');
      }
    } else {
      print('❌ Query failed with status code: ${response.statusCode}');
      print('   Response: ${response.body}');
    }
  } catch (e) {
    print('❌ Failed to send query: $e');
  }

  print('\n🎉 API Integration Test Complete!');
  print(
      '\n📱 Your Flutter app should now be running at: http://localhost:3001');
  print('🔗 API URL: $baseUrl');
  print('💡 Try sending a message in the Flutter app chat interface!');
}
