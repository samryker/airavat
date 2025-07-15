import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';

class TwinService {
  static final FirebaseFirestore _firestore = FirebaseFirestore.instance;
  static final FirebaseAuth _auth = FirebaseAuth.instance;

  // Get current user ID
  static String? get currentUserId => _auth.currentUser?.uid;

  // Save user's 3D twin customization
  static Future<void> saveTwinCustomization({
    required String userId,
    required Map<String, dynamic> biomarkers,
    Map<String, String>? organColors,
    List<String>? highlightedOrgans,
  }) async {
    try {
      await _firestore.collection('twin_customizations').doc(userId).set({
        'userId': userId,
        'biomarkers': biomarkers,
        'organColors': organColors ?? {},
        'highlightedOrgans': highlightedOrgans ?? [],
        'lastUpdated': FieldValue.serverTimestamp(),
      });
    } catch (e) {
      throw Exception('Failed to save twin customization: $e');
    }
  }

  // Get user's 3D twin customization
  static Future<Map<String, dynamic>?> getTwinCustomization(
      String userId) async {
    try {
      final doc =
          await _firestore.collection('twin_customizations').doc(userId).get();

      if (doc.exists) {
        return doc.data();
      }
      return null;
    } catch (e) {
      throw Exception('Failed to get twin customization: $e');
    }
  }

  // Save user biomarkers
  static Future<void> saveBiomarkers({
    required String userId,
    required Map<String, dynamic> biomarkers,
    String? reportType,
  }) async {
    try {
      await _firestore
          .collection('biomarkers')
          .doc(userId)
          .collection('reports')
          .add({
        'biomarkers': biomarkers,
        'reportType': reportType ?? 'general',
        'timestamp': FieldValue.serverTimestamp(),
      });
    } catch (e) {
      throw Exception('Failed to save biomarkers: $e');
    }
  }

  // Get latest user biomarkers
  static Future<Map<String, dynamic>?> getLatestBiomarkers(
      String userId) async {
    try {
      final query = await _firestore
          .collection('biomarkers')
          .doc(userId)
          .collection('reports')
          .orderBy('timestamp', descending: true)
          .limit(1)
          .get();

      if (query.docs.isNotEmpty) {
        return query.docs.first.data();
      }
      return null;
    } catch (e) {
      throw Exception('Failed to get biomarkers: $e');
    }
  }

  // Get all user biomarkers
  static Future<List<Map<String, dynamic>>> getAllBiomarkers(
      String userId) async {
    try {
      final query = await _firestore
          .collection('biomarkers')
          .doc(userId)
          .collection('reports')
          .orderBy('timestamp', descending: true)
          .get();

      return query.docs.map((doc) => doc.data()).toList();
    } catch (e) {
      throw Exception('Failed to get all biomarkers: $e');
    }
  }

  // Update organ colors for user
  static Future<void> updateOrganColors({
    required String userId,
    required Map<String, String> organColors,
  }) async {
    try {
      await _firestore.collection('twin_customizations').doc(userId).update({
        'organColors': organColors,
        'lastUpdated': FieldValue.serverTimestamp(),
      });
    } catch (e) {
      throw Exception('Failed to update organ colors: $e');
    }
  }

  // Highlight specific organs for user
  static Future<void> highlightOrgans({
    required String userId,
    required List<String> organs,
  }) async {
    try {
      await _firestore.collection('twin_customizations').doc(userId).update({
        'highlightedOrgans': organs,
        'lastUpdated': FieldValue.serverTimestamp(),
      });
    } catch (e) {
      throw Exception('Failed to highlight organs: $e');
    }
  }

  // Create default twin customization for new user
  static Future<void> createDefaultTwin(String userId) async {
    try {
      await saveTwinCustomization(
        userId: userId,
        biomarkers: {
          'hemoglobin': 14.0,
          'white_blood_cells': 7.5,
          'platelets': 250,
          'creatinine': 1.0,
          'glucose': 100,
        },
        organColors: {
          'Kidney-Left': '#00ff00',
          'Kidney-Right': '#00ff00',
          'Stomach': '#ffff00',
          'Pancreas': '#ff00ff',
          'Femur': '#0000ff',
        },
        highlightedOrgans: [],
      );
    } catch (e) {
      throw Exception('Failed to create default twin: $e');
    }
  }
}
