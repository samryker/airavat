import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:firebase_auth/firebase_auth.dart';
import '../config/backend_config.dart';

class DigitalTwinPayload {
  final double heightCm;
  final double weightKg;
  final Map<String, double>? biomarkers;

  DigitalTwinPayload({
    required this.heightCm,
    required this.weightKg,
    this.biomarkers,
  });

  Map<String, dynamic> toJson() => {
        'height_cm': heightCm,
        'weight_kg': weightKg,
        if (biomarkers != null) 'biomarkers': biomarkers,
      };
}

class DigitalTwinRecord extends DigitalTwinPayload {
  final String patientId;
  final String? updatedAt;

  DigitalTwinRecord({
    required this.patientId,
    required double heightCm,
    required double weightKg,
    Map<String, double>? biomarkers,
    this.updatedAt,
  }) : super(heightCm: heightCm, weightKg: weightKg, biomarkers: biomarkers);

  factory DigitalTwinRecord.fromJson(Map<String, dynamic> json) {
    final biomarkers = (json['biomarkers'] as Map?)
        ?.map((k, v) => MapEntry(k.toString(), (v as num).toDouble()));
    return DigitalTwinRecord(
      patientId: json['patient_id']?.toString() ?? '',
      heightCm: (json['height_cm'] as num).toDouble(),
      weightKg: (json['weight_kg'] as num).toDouble(),
      biomarkers: biomarkers,
      updatedAt: json['updated_at']?.toString(),
    );
  }
}

class TreatmentUpdatePayload extends DigitalTwinPayload {
  final String report;

  TreatmentUpdatePayload({
    required this.report,
    required double heightCm,
    required double weightKg,
    Map<String, double>? biomarkers,
  }) : super(heightCm: heightCm, weightKg: weightKg, biomarkers: biomarkers);

  @override
  Map<String, dynamic> toJson() => {
        ...super.toJson(),
        'report': report,
      };
}

class TreatmentUpdateResponse {
  final DigitalTwinRecord twin;
  final String inference;
  final bool stored;

  TreatmentUpdateResponse({
    required this.twin,
    required this.inference,
    required this.stored,
  });

  factory TreatmentUpdateResponse.fromJson(Map<String, dynamic> json) {
    return TreatmentUpdateResponse(
      twin: DigitalTwinRecord.fromJson(json['twin'] as Map<String, dynamic>),
      inference: json['inference']?.toString() ?? '',
      stored: json['stored'] == true,
    );
  }
}

class DigitalTwinService {
  static const String _base = BackendConfig.baseUrl;
  static String? get _userId => FirebaseAuth.instance.currentUser?.uid;

  static Future<Map<String, dynamic>> health() async {
    final res = await http.get(Uri.parse('$_base/digital_twin/health'));
    if (res.statusCode == 200) {
      return jsonDecode(res.body) as Map<String, dynamic>;
    }
    throw Exception('Digital twin health failed: ${res.statusCode}');
  }

  static Future<DigitalTwinRecord> upsertTwin(DigitalTwinPayload payload,
      {String? patientId}) async {
    final id = patientId ?? _userId;
    if (id == null) throw Exception('User not authenticated');
    final res = await http.put(
      Uri.parse('$_base/digital_twin/$id'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(payload.toJson()),
    );
    if (res.statusCode == 200) {
      return DigitalTwinRecord.fromJson(jsonDecode(res.body));
    }
    throw Exception(
        'Upsert twin failed: ${res.statusCode} - ${res.body.toString()}');
  }

  static Future<DigitalTwinRecord> getTwin({String? patientId}) async {
    final id = patientId ?? _userId;
    if (id == null) throw Exception('User not authenticated');
    final res = await http.get(Uri.parse('$_base/digital_twin/$id'));
    if (res.statusCode == 200) {
      return DigitalTwinRecord.fromJson(jsonDecode(res.body));
    }
    throw Exception('Get twin failed: ${res.statusCode} - ${res.body}');
  }

  static Future<TreatmentUpdateResponse> processTreatment(
    TreatmentUpdatePayload payload, {
    String? patientId,
  }) async {
    final id = patientId ?? _userId;
    if (id == null) throw Exception('User not authenticated');
    final res = await http.post(
      Uri.parse('$_base/digital_twin/$id/treatment'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(payload.toJson()),
    );
    if (res.statusCode == 200) {
      return TreatmentUpdateResponse.fromJson(jsonDecode(res.body));
    }
    throw Exception(
        'Process treatment failed: ${res.statusCode} - ${res.body}');
  }

  /// Get live twin data combining SMPL + biomarkers using existing Cloud Run endpoints
  static Future<Map<String, dynamic>> getLiveTwinData(
      {String? patientId}) async {
    final id = patientId ?? _userId;
    if (id == null) throw Exception('User not authenticated');

    try {
      // Get SMPL twin data from existing endpoint
      Map<String, dynamic> smplData = {};
      try {
        final twinRes = await http.get(Uri.parse('$_base/digital_twin/$id'));
        if (twinRes.statusCode == 200) {
          smplData = jsonDecode(twinRes.body) as Map<String, dynamic>;
        }
      } catch (e) {
        print('SMPL data not available: $e');
      }

      // Get biomarkers from agent endpoint
      Map<String, dynamic> biomarkers = {};
      try {
        final bioRes = await http.get(
            Uri.parse('${BackendConfig.baseUrl}/agent/patient/$id/biomarkers'));
        if (bioRes.statusCode == 200) {
          final bioData = jsonDecode(bioRes.body);
          if (bioData['status'] == 'success') {
            biomarkers = bioData['biomarkers'] ?? {};
          }
        }
      } catch (e) {
        print('Biomarker data not available: $e');
      }

      // Combine data
      return {
        'patient_id': id,
        'smpl_data': smplData,
        'biomarkers': biomarkers,
        'last_updated': DateTime.now().toIso8601String(),
        'data_sources': {
          'smpl': smplData.isNotEmpty,
          'biomarkers': biomarkers.isNotEmpty,
        }
      };
    } catch (e) {
      throw Exception('Get live twin data failed: $e');
    }
  }

  /// Update biomarkers using existing twin upsert endpoint
  static Future<Map<String, dynamic>> updateBiomarkers(
    Map<String, dynamic> biomarkers, {
    String? patientId,
  }) async {
    final id = patientId ?? _userId;
    if (id == null) throw Exception('User not authenticated');

    try {
      // Get current twin data
      DigitalTwinRecord? currentTwin;
      try {
        currentTwin = await getTwin(patientId: id);
      } catch (e) {
        print('No existing twin found, creating new one');
      }

      // Create/update twin with biomarkers
      final payload = DigitalTwinPayload(
        heightCm: currentTwin?.heightCm ?? 170.0,
        weightKg: currentTwin?.weightKg ?? 70.0,
        biomarkers: biomarkers
            .map((k, v) => MapEntry(k, (v is num) ? v.toDouble() : 0.0)),
      );

      await upsertTwin(payload, patientId: id);

      return {
        'status': 'success',
        'message': 'Biomarkers updated successfully',
        'patient_id': id,
        'biomarker_count': biomarkers.length,
        'twin_updated': true
      };
    } catch (e) {
      throw Exception('Update biomarkers failed: $e');
    }
  }
}
