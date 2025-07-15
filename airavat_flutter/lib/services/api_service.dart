import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:firebase_auth/firebase_auth.dart';
import 'package:cloud_firestore/cloud_firestore.dart';

class ApiService {
  static const String baseUrl =
      'https://airavat-fastapi-124145466298.us-central1.run.app';

  // Get the current user's ID for API calls
  static String? get currentUserId {
    return FirebaseAuth.instance.currentUser?.uid;
  }

  // Get patient context from Firebase for API calls
  static Future<Map<String, dynamic>?> getPatientContext() async {
    try {
      final userId = currentUserId;
      if (userId == null) return null;

      final doc = await FirebaseFirestore.instance
          .collection('patients')
          .doc(userId)
          .get();

      if (doc.exists) {
        return doc.data();
      }
      return null;
    } catch (e) {
      print('Error getting patient context: $e');
      return null;
    }
  }

  // Send a query to the AI agent with patient context
  static Future<Map<String, dynamic>> sendQuery({
    required String queryText,
    List<String>? symptoms,
    List<String>? medicalHistory,
    List<String>? currentMedications,
    Map<String, dynamic>? additionalData,
  }) async {
    try {
      final userId = currentUserId;
      print('API Service: User ID = $userId');
      if (userId == null) {
        throw Exception('User not authenticated');
      }

      // Get patient context from Firebase
      final patientContext = await getPatientContext();

      final requestBody = {
        'patient_id': userId,
        'query_text': queryText,
        'symptoms': symptoms,
        'medical_history': medicalHistory,
        'current_medications': currentMedications,
        'additional_data': {
          ...?additionalData,
          'patient_context': patientContext, // Include patient context
        },
      };

      print('API Service: Sending request to $baseUrl/agent/query');
      print('API Service: Request body = $requestBody');

      final response = await http.post(
        Uri.parse('$baseUrl/agent/query'),
        headers: {
          'Content-Type': 'application/json',
        },
        body: jsonEncode(requestBody),
      );

      print('API Service: Response status = ${response.statusCode}');
      print('API Service: Response body = ${response.body}');

      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      } else {
        throw Exception(
            'Failed to get response: ${response.statusCode} - ${response.body}');
      }
    } catch (e) {
      print('API Service: Error = $e');
      throw Exception('Error sending query: $e');
    }
  }

  // Get complete patient context from backend
  static Future<Map<String, dynamic>> getPatientContextFromBackend() async {
    try {
      final userId = currentUserId;
      if (userId == null) {
        throw Exception('User not authenticated');
      }

      final response = await http.get(
        Uri.parse('$baseUrl/agent/patient/$userId/context'),
        headers: {
          'Content-Type': 'application/json',
        },
      );

      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      } else {
        throw Exception(
            'Failed to get patient context: ${response.statusCode} - ${response.body}');
      }
    } catch (e) {
      print('API Service: Error getting patient context = $e');
      throw Exception('Error getting patient context: $e');
    }
  }

  // Get conversation history
  static Future<Map<String, dynamic>> getConversationHistory(
      {int limit = 10}) async {
    try {
      final userId = currentUserId;
      if (userId == null) {
        throw Exception('User not authenticated');
      }

      final response = await http.get(
        Uri.parse(
            '$baseUrl/agent/patient/$userId/conversation-history?limit=$limit'),
        headers: {
          'Content-Type': 'application/json',
        },
      );

      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      } else {
        throw Exception(
            'Failed to get conversation history: ${response.statusCode} - ${response.body}');
      }
    } catch (e) {
      print('API Service: Error getting conversation history = $e');
      throw Exception('Error getting conversation history: $e');
    }
  }

  // Update treatment plan
  static Future<Map<String, dynamic>> updateTreatmentPlan(
      Map<String, dynamic> treatmentPlan) async {
    try {
      final userId = currentUserId;
      if (userId == null) {
        throw Exception('User not authenticated');
      }

      final response = await http.post(
        Uri.parse('$baseUrl/agent/patient/$userId/treatment-plan'),
        headers: {
          'Content-Type': 'application/json',
        },
        body: jsonEncode(treatmentPlan),
      );

      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      } else {
        throw Exception(
            'Failed to update treatment plan: ${response.statusCode} - ${response.body}');
      }
    } catch (e) {
      print('API Service: Error updating treatment plan = $e');
      throw Exception('Error updating treatment plan: $e');
    }
  }

  // Get patient biomarkers
  static Future<Map<String, dynamic>> getPatientBiomarkers() async {
    try {
      final userId = currentUserId;
      if (userId == null) {
        throw Exception('User not authenticated');
      }

      final response = await http.get(
        Uri.parse('$baseUrl/agent/patient/$userId/biomarkers'),
        headers: {
          'Content-Type': 'application/json',
        },
      );

      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      } else {
        throw Exception(
            'Failed to get biomarkers: ${response.statusCode} - ${response.body}');
      }
    } catch (e) {
      print('API Service: Error getting biomarkers = $e');
      throw Exception('Error getting biomarkers: $e');
    }
  }

  // Submit feedback for a previous query
  static Future<Map<String, dynamic>> submitFeedback({
    required String requestId,
    required bool outcomeWorks,
    String? feedbackText,
  }) async {
    try {
      final userId = currentUserId;
      if (userId == null) {
        throw Exception('User not authenticated');
      }

      final response = await http.post(
        Uri.parse('$baseUrl/agent/patient/$userId/feedback'),
        headers: {
          'Content-Type': 'application/json',
        },
        body: jsonEncode({
          'request_id': requestId,
          'outcome_works': outcomeWorks,
          'feedback_text': feedbackText,
        }),
      );

      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      } else {
        throw Exception(
            'Failed to submit feedback: ${response.statusCode} - ${response.body}');
      }
    } catch (e) {
      throw Exception('Error submitting feedback: $e');
    }
  }

  // Test the API connection
  static Future<bool> testConnection() async {
    try {
      final response = await http.get(Uri.parse('$baseUrl/'));
      return response.statusCode == 200;
    } catch (e) {
      return false;
    }
  }
}
