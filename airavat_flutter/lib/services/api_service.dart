import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:firebase_auth/firebase_auth.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'dart:typed_data';
import 'package:http_parser/http_parser.dart';
import '../config/backend_config.dart';

class ApiService {
  static const String baseUrl = BackendConfig.baseUrl;

  // Get the current user's ID for API calls
  static String? get currentUserId {
    return FirebaseAuth.instance.currentUser?.uid;
  }

  // Get patient context from Firebase for API calls (includes latest treatment)
  static Future<Map<String, dynamic>?> getPatientContext() async {
    try {
      final userId = currentUserId;
      if (userId == null) return null;

      // Get patient profile data
      final patientDoc = await FirebaseFirestore.instance
          .collection('patients')
          .doc(userId)
          .get();

      if (!patientDoc.exists) return null;

      final patientData = patientDoc.data()!;

      // Get latest treatment data
      final latestTreatmentDoc = await FirebaseFirestore.instance
          .collection('latest_treatment')
          .doc(userId)
          .get();

      if (latestTreatmentDoc.exists) {
        final latestTreatment = latestTreatmentDoc.data()!;
        patientData['latest_treatment'] = latestTreatment['treatment_data'];
        patientData['latest_treatment_date'] = latestTreatment['date'];
      }

      return patientData;
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

      // Get patient context from Firebase and ensure it's serializable
      final patientContext = await getPatientContext();

      // Clean and serialize the patient context to ensure it's JSON-safe
      Map<String, dynamic>? cleanPatientContext;
      if (patientContext != null) {
        cleanPatientContext = _cleanForJsonSerialization(patientContext);
      }

      // Clean additional data as well
      Map<String, dynamic>? cleanAdditionalData;
      if (additionalData != null) {
        cleanAdditionalData = _cleanForJsonSerialization(additionalData);
      }

      final requestBody = {
        'patient_id': userId,
        'query_text': queryText,
        'symptoms': symptoms,
        'medical_history': medicalHistory,
        'current_medications': currentMedications,
        'additional_data': {
          ...?cleanAdditionalData,
          'patient_context': cleanPatientContext,
        },
      };

      print('API Service: Sending request to $baseUrl/gemini/suggest');
      print('API Service: Request body = $requestBody');

      final response = await http.post(
        Uri.parse('$baseUrl/gemini/suggest'),
        headers: {
          'Content-Type': 'application/json',
        },
        body: jsonEncode(requestBody),
      );

      print('API Service: Response status = ${response.statusCode}');
      print('API Service: Response body = ${response.body}');

      if (response.statusCode == 200) {
        final responseData = jsonDecode(response.body);

        // Convert new Gemini response format to expected format
        return {
          'response_text': responseData['text'] ?? 'No response received',
          'request_id': responseData['request_id'] ??
              DateTime.now().millisecondsSinceEpoch.toString(),
          'suggestions': responseData['features'] != null
              ? [
                  {
                    'suggestion_text': 'Consult with a healthcare professional',
                    'confidence_score': 0.9
                  }
                ]
              : [],
          'features': responseData['features']
        };
      } else {
        throw Exception(
            'Failed to get response: ${response.statusCode} - ${response.body}');
      }
    } catch (e) {
      print('API Service: Error = $e');
      throw Exception('Error sending query: $e');
    }
  }

  // Upload file for analysis
  static Future<Map<String, dynamic>> uploadFileForAnalysis({
    required Uint8List fileBytes,
    required String fileName,
    required String fileType,
  }) async {
    try {
      final userId = currentUserId;
      if (userId == null) {
        throw Exception('User not authenticated');
      }

      // Create multipart request
      var request = http.MultipartRequest(
        'POST',
        Uri.parse('$baseUrl/upload/analyze'),
      );

      // Add file
      request.files.add(
        http.MultipartFile.fromBytes(
          'file',
          fileBytes,
          filename: fileName,
        ),
      );

      // Add form fields
      request.fields['patient_id'] = userId;
      request.fields['file_type'] = fileType;

      print('API Service: Uploading file $fileName of type $fileType');

      final streamedResponse = await request.send();
      final response = await http.Response.fromStream(streamedResponse);

      print('API Service: Upload response status = ${response.statusCode}');
      print('API Service: Upload response body = ${response.body}');

      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      } else {
        throw Exception(
            'Failed to upload file: ${response.statusCode} - ${response.body}');
      }
    } catch (e) {
      print('API Service: Upload error = $e');
      throw Exception('Error uploading file: $e');
    }
  }

  // Get cost estimate for a query
  static Future<Map<String, dynamic>> getCostEstimate({
    required String queryText,
  }) async {
    try {
      final userId = currentUserId;
      if (userId == null) {
        throw Exception('User not authenticated');
      }

      final response = await http.get(
        Uri.parse(
            '$baseUrl/cost/estimate?patient_id=$userId&query_text=${Uri.encodeComponent(queryText)}'),
        headers: {
          'Content-Type': 'application/json',
        },
      );

      print(
          'API Service: Cost estimate response status = ${response.statusCode}');
      print('API Service: Cost estimate response body = ${response.body}');

      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      } else {
        throw Exception(
            'Failed to get cost estimate: ${response.statusCode} - ${response.body}');
      }
    } catch (e) {
      print('API Service: Cost estimate error = $e');
      throw Exception('Error getting cost estimate: $e');
    }
  }

  // Helper method to clean objects for JSON serialization
  static Map<String, dynamic> _cleanForJsonSerialization(
      Map<String, dynamic> data) {
    Map<String, dynamic> cleaned = {};

    data.forEach((key, value) {
      if (value == null) {
        cleaned[key] = null;
      } else if (value is String ||
          value is int ||
          value is double ||
          value is bool) {
        cleaned[key] = value;
      } else if (value is List) {
        cleaned[key] = value.map((item) {
          if (item is Map<String, dynamic>) {
            return _cleanForJsonSerialization(item);
          } else if (item is String ||
              item is int ||
              item is double ||
              item is bool) {
            return item;
          } else {
            return item.toString();
          }
        }).toList();
      } else if (value is Map<String, dynamic>) {
        cleaned[key] = _cleanForJsonSerialization(value);
      } else {
        // Convert any other type to string
        cleaned[key] = value.toString();
      }
    });

    return cleaned;
  }

  // Get complete patient context from backend
  static Future<Map<String, dynamic>> getPatientContextFromBackend() async {
    // Deprecated server path. Keep for compatibility but redirect to local Firebase context.
    final ctx = await getPatientContext();
    return {
      'status': 'success',
      'context': _cleanForJsonSerialization(ctx ?? {}),
    };
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

  // Update treatment plan with date-based logic
  static Future<Map<String, dynamic>> updateTreatmentPlan(
      Map<String, dynamic> treatmentPlan) async {
    try {
      final userId = currentUserId;
      if (userId == null) {
        throw Exception('User not authenticated');
      }

      final user = FirebaseAuth.instance.currentUser!;
      final now = DateTime.now();
      final today = DateTime(now.year, now.month, now.day);

      // Get current patient document to check existing treatments
      final patientDoc = await FirebaseFirestore.instance
          .collection('patients')
          .doc(userId)
          .get();

      Map<String, dynamic> updateData = {
        'email': user.email,
        'updatedAt': FieldValue.serverTimestamp(),
        'lastTreatmentUpdate': FieldValue.serverTimestamp(),
      };

      if (patientDoc.exists) {
        final patientData = patientDoc.data()!;
        final existingTreatments = patientData['treatmentPlans'] as List? ?? [];

        // Check if there's already a treatment from today
        bool hasTodayTreatment = false;
        for (var treatment in existingTreatments) {
          if (treatment['timestamp'] != null) {
            final treatmentDate = DateTime.tryParse(treatment['timestamp']);
            if (treatmentDate != null) {
              final treatmentDay = DateTime(
                  treatmentDate.year, treatmentDate.month, treatmentDate.day);
              if (treatmentDay.isAtSameMomentAs(today)) {
                hasTodayTreatment = true;
                break;
              }
            }
          }
        }

        if (hasTodayTreatment) {
          // Same day: Append to existing treatmentPlans array
          updateData['treatmentPlans'] = FieldValue.arrayUnion([treatmentPlan]);

          await FirebaseFirestore.instance
              .collection('patients')
              .doc(userId)
              .set(updateData, SetOptions(merge: true));

          return {
            'status': 'success',
            'message':
                'Treatment appended to today\'s plans in patient profile',
            'patient_id': userId,
            'action': 'appended_same_day',
          };
        } else {
          // Different day: Update latest_treatment collection AND add to treatmentPlans
          updateData['treatmentPlans'] = FieldValue.arrayUnion([treatmentPlan]);

          // Update main patient document
          await FirebaseFirestore.instance
              .collection('patients')
              .doc(userId)
              .set(updateData, SetOptions(merge: true));

          // Save as latest treatment in separate collection
          await FirebaseFirestore.instance
              .collection('latest_treatment')
              .doc(userId)
              .set({
            'patient_id': userId,
            'treatment_data': treatmentPlan,
            'created_at': FieldValue.serverTimestamp(),
            'date': today.toIso8601String().split('T')[0], // YYYY-MM-DD format
          });

          return {
            'status': 'success',
            'message':
                'New treatment saved to patient profile and latest_treatment collection',
            'patient_id': userId,
            'action': 'new_day_treatment',
          };
        }
      } else {
        // First time user: Create patient document and latest_treatment
        updateData['treatmentPlans'] = [treatmentPlan];

        await FirebaseFirestore.instance
            .collection('patients')
            .doc(userId)
            .set(updateData, SetOptions(merge: true));

        // Save as latest treatment
        await FirebaseFirestore.instance
            .collection('latest_treatment')
            .doc(userId)
            .set({
          'patient_id': userId,
          'treatment_data': treatmentPlan,
          'created_at': FieldValue.serverTimestamp(),
          'date': today.toIso8601String().split('T')[0],
        });

        return {
          'status': 'success',
          'message': 'Patient profile created with first treatment',
          'patient_id': userId,
          'action': 'first_treatment',
        };
      }
    } catch (e) {
      print('API Service: Error updating treatment plan = $e');
      throw Exception('Error updating treatment plan: $e');
    }
  }

  // Alternative method using TreatmentPlanUpdate model
  static Future<Map<String, dynamic>> updateTreatmentPlanAlt(
      Map<String, dynamic> treatmentPlan) async {
    try {
      final userId = currentUserId;
      if (userId == null) {
        throw Exception('User not authenticated');
      }

      // Format data for TreatmentPlanUpdate model
      final requestData = {
        'patient_id': userId,
        'treatment_plan': treatmentPlan,
        'plan_type': treatmentPlan['plan_type'] ?? 'ai_guidance',
        'priority': treatmentPlan['priority'] ?? 'medium',
        'notes': 'Generated by AI assistant',
      };

      final response = await http.post(
        Uri.parse('$baseUrl/agent/update_treatment_plan'),
        headers: {
          'Content-Type': 'application/json',
        },
        body: jsonEncode(requestData),
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

  // Analyze a file using Gemini
  static Future<Map<String, dynamic>> analyzeFile({
    required Uint8List fileBytes,
    required String filename,
    String contentType = 'application/octet-stream',
  }) async {
    try {
      final userId = currentUserId;
      if (userId == null) throw Exception('User not authenticated');

      final uri = Uri.parse('$baseUrl/upload/analyze');
      final request = http.MultipartRequest('POST', uri);
      request.files.add(http.MultipartFile.fromBytes(
        'file',
        fileBytes,
        filename: filename,
        contentType: MediaType.parse(contentType),
      ));
      request.fields['patient_id'] = userId;
      request.fields['file_type'] = _inferFileType(filename);

      final streamed = await request.send();
      final response = await http.Response.fromStream(streamed);
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        // Normalize to legacy format expected by callers
        final fileAnalysis =
            (data['file_analysis'] ?? {}) as Map<String, dynamic>;
        return {
          'status': 'success',
          'analysis': fileAnalysis['gemini_response'] ?? 'Analysis complete',
          'raw': data,
        };
      }
      throw Exception(
          'Analyze failed: ${response.statusCode} - ${response.body}');
    } catch (e) {
      throw Exception('Error analyzing file: $e');
    }
  }

  static String _inferFileType(String filename) {
    final ext = filename.toLowerCase().split('.').last;
    switch (ext) {
      case 'pdf':
      case 'txt':
      case 'doc':
      case 'docx':
        return 'text';
      case 'jpg':
      case 'jpeg':
      case 'png':
        return 'image';
      default:
        return 'unknown';
    }
  }

  // Test the API connection
  static Future<bool> testConnection() async {
    try {
      final response = await http.get(Uri.parse('$baseUrl/health'));
      return response.statusCode == 200;
    } catch (e) {
      return false;
    }
  }

  // Ensure patient document exists and add treatment plan
  static Future<Map<String, dynamic>> saveTreatmentToProfile(
      Map<String, dynamic> treatmentData) async {
    try {
      final userId = currentUserId;
      if (userId == null) {
        throw Exception('User not authenticated');
      }

      // Create a complete patient document structure
      final patientData = {
        'email': FirebaseAuth.instance.currentUser?.email ?? '',
        'display_name':
            FirebaseAuth.instance.currentUser?.displayName ?? 'User',
        'treatmentPlans': [treatmentData],
        'updatedAt': DateTime.now().toIso8601String(),
        'createdAt': DateTime.now().toIso8601String(),
        'lastLogin': DateTime.now().toIso8601String(),
        'isActive': true,
        'emailVerified':
            FirebaseAuth.instance.currentUser?.emailVerified ?? false,
      };

      // Directly update Firestore via Firebase Admin
      await FirebaseFirestore.instance.collection('patients').doc(userId).set({
        'treatmentPlans': FieldValue.arrayUnion([treatmentData]),
        'updatedAt': FieldValue.serverTimestamp(),
        'lastTreatmentUpdate': FieldValue.serverTimestamp(),
      }, SetOptions(merge: true));

      return {
        'status': 'success',
        'message': 'Treatment plan saved successfully',
        'patient_id': userId,
      };
    } catch (e) {
      print('Direct Firestore save error: $e');
      throw Exception('Error saving to profile: $e');
    }
  }

  // Get user notifications (tasks/reminders/appointments)
  static Future<List<Map<String, dynamic>>> getUserNotifications(
      String userId) async {
    try {
      // Try the backend notification endpoint first
      final response = await http.get(
        Uri.parse('$baseUrl/notifications/user/$userId'),
        headers: {'Content-Type': 'application/json'},
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        if (data['success'] == true || data['status'] == 'success') {
          return List<Map<String, dynamic>>.from(data['notifications'] ?? []);
        }
      }

      // If new endpoint fails, try alternative Firestore approach
      try {
        final firebaseNotifications = await FirebaseFirestore.instance
            .collection('notifications')
            .where('user_id', isEqualTo: userId)
            .orderBy('created_at', descending: true)
            .limit(20)
            .get();

        return firebaseNotifications.docs.map((doc) {
          final data = doc.data();
          return {
            'id': doc.id,
            'title': data['title'] ?? 'Notification',
            'message': data['message'] ?? '',
            'notification_type': data['type'] ?? 'general_reminder',
            'priority': data['priority'] ?? 'medium',
            'status': data['status'] ?? 'pending',
            'created_at':
                data['created_at'] ?? DateTime.now().toIso8601String(),
            'scheduled_time': data['scheduled_time'],
          };
        }).toList();
      } catch (firebaseError) {
        print('Error fetching from Firebase: $firebaseError');
      }

      return [];
    } catch (e) {
      print('Error fetching notifications: $e');
      return [];
    }
  }

  // Create a new notification/reminder
  static Future<Map<String, dynamic>> createNotification({
    required String userId,
    required String title,
    required String message,
    String notificationType = 'general_reminder',
    String priority = 'medium',
    String? scheduledTime,
    String? recipientEmail,
  }) async {
    try {
      // Try the backend notification endpoint
      final response = await http.post(
        Uri.parse('$baseUrl/notifications/create'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({
          'user_id': userId,
          'title': title,
          'message': message,
          'notification_type': notificationType,
          'priority': priority,
          'scheduled_time': scheduledTime ??
              DateTime.now().add(Duration(minutes: 5)).toIso8601String(),
        }),
      );

      if (response.statusCode == 200) {
        final result = json.decode(response.body);
        if (result['success'] == true) {
          return result;
        }
      }

      // Fallback: Create directly in Firestore
      try {
        final notificationData = {
          'user_id': userId,
          'notification_type': notificationType,
          'title': title,
          'message': message,
          'priority': priority,
          'scheduled_time': scheduledTime ??
              DateTime.now().add(Duration(minutes: 5)).toIso8601String(),
          'created_at': DateTime.now().toIso8601String(),
          'status': 'pending',
        };

        await FirebaseFirestore.instance
            .collection('notifications')
            .add(notificationData);

        return {
          'success': true,
          'message': 'Notification created successfully',
        };
      } catch (firebaseError) {
        print('Error creating notification in Firebase: $firebaseError');
        throw Exception('Failed to create notification: $firebaseError');
      }
    } catch (e) {
      throw Exception('Error creating notification: $e');
    }
  }
}
