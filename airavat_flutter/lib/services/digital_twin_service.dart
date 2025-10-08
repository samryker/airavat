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
    // Handle biomarkers with proper null/num conversion
    Map<String, double>? biomarkers;
    try {
      biomarkers = (json['biomarkers'] as Map?)?.map(
        (k, v) => MapEntry(
          k.toString(),
          v == null
              ? 0.0
              : (v is num
                  ? v.toDouble()
                  : double.tryParse(v.toString()) ?? 0.0),
        ),
      );
    } catch (e) {
      print('Error parsing biomarkers: $e');
      biomarkers = {};
    }

    // Helper to safely parse numeric values
    double parseDouble(dynamic value, double defaultValue) {
      if (value == null) return defaultValue;
      if (value is num) return value.toDouble();
      if (value is String) return double.tryParse(value) ?? defaultValue;
      return defaultValue;
    }

    return DigitalTwinRecord(
      patientId: json['patient_id']?.toString() ?? '',
      heightCm: parseDouble(json['height_cm'], 170.0),
      weightKg: parseDouble(json['weight_kg'], 70.0),
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
    final res = await http.get(Uri.parse('$_base/health'));
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
      final body = jsonDecode(res.body);
      // Accept either wrapped {status, twin:{...}} or raw twin JSON
      final twinJson = (body is Map<String, dynamic> && body['twin'] != null)
          ? body['twin'] as Map<String, dynamic>
          : (body as Map<String, dynamic>);
      return DigitalTwinRecord.fromJson(twinJson);
    }
    throw Exception(
        'Upsert twin failed: ${res.statusCode} - ${res.body.toString()}');
  }

  static Future<DigitalTwinRecord> getTwin({String? patientId}) async {
    final id = patientId ?? _userId;
    if (id == null) throw Exception('User not authenticated');
    final res = await http.get(Uri.parse('$_base/digital_twin/$id'));
    if (res.statusCode == 200) {
      final body = jsonDecode(res.body);
      final twinJson = (body is Map<String, dynamic> && body['twin'] != null)
          ? body['twin'] as Map<String, dynamic>
          : (body as Map<String, dynamic>);
      return DigitalTwinRecord.fromJson(twinJson);
    }
    throw Exception('Get twin failed: ${res.statusCode} - ${res.body}');
  }

  static Future<TreatmentUpdateResponse> processTreatment(
    TreatmentUpdatePayload payload, {
    String? patientId,
  }) async {
    // Hybrid summary via both services: upload analyze (Gemini) + genetic analyze (HF)
    final id = patientId ?? _userId;
    if (id == null) throw Exception('User not authenticated');

    // 1) Ensure twin is saved with latest measurements and biomarkers
    await upsertTwin(
        DigitalTwinPayload(
          heightCm: payload.heightCm,
          weightKg: payload.weightKg,
          biomarkers: payload.biomarkers,
        ),
        patientId: id);

    // 2) Call genetic analysis if biomarkers or report exist
    Map<String, dynamic>? genetic;
    try {
      if ((payload.report.isNotEmpty) ||
          ((payload.biomarkers ?? {}).isNotEmpty)) {
        // Use multipart form data (not JSON) as backend expects Form fields
        final request = http.MultipartRequest(
          'POST',
          Uri.parse('$_base/genetic/analyze'),
        );
        
        // Add text field as Form data
        request.fields['text'] = payload.report.isNotEmpty
            ? payload.report
            : 'Biomarkers: ${payload.biomarkers}';
        request.fields['user_id'] = id;
        request.fields['report_type'] = 'biomarkers';
        
        final streamedResponse = await request.send();
        final res = await http.Response.fromStream(streamedResponse);
        
        if (res.statusCode == 200) {
          genetic = jsonDecode(res.body) as Map<String, dynamic>;
        }
      }
    } catch (_) {}

    // 3) Ask Gemini for treatment suggestion with a concise context
    final conciseContext = {
      'height_cm': payload.heightCm,
      'weight_kg': payload.weightKg,
      'biomarkers': payload.biomarkers ?? {},
      if (genetic != null) 'genetic_summary': genetic['analysis'] ?? genetic,
    };

    final requestBody = {
      'patient_id': id,
      'query_text': 'Provide treatment guidance for the current status.',
      'additional_data': {'patient_context': conciseContext},
    };

    final geminiRes = await http.post(
      Uri.parse('$_base/gemini/suggest'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(requestBody),
    );

    String inference = '';
    if (geminiRes.statusCode == 200) {
      final data = jsonDecode(geminiRes.body);
      inference = data['text']?.toString() ?? '';
    } else {
      throw Exception(
          'Gemini summary failed: ${geminiRes.statusCode} - ${geminiRes.body}');
    }

    return TreatmentUpdateResponse(
      twin: await getTwin(patientId: id),
      inference: inference,
      stored: true,
    );
  }

  /// Get live twin data combining current twin + (optional) biomarkers (from twin only)
  static Future<Map<String, dynamic>> getLiveTwinData(
      {String? patientId}) async {
    final id = patientId ?? _userId;
    if (id == null) throw Exception('User not authenticated');

    try {
      // Get twin data (also contains last saved biomarkers)
      final twinRes = await http.get(Uri.parse('$_base/digital_twin/$id'));
      Map<String, dynamic> twinJson = {};
      DigitalTwinRecord? twin;
      if (twinRes.statusCode == 200) {
        final body = jsonDecode(twinRes.body);
        twinJson = (body is Map<String, dynamic> && body['twin'] != null)
            ? body['twin'] as Map<String, dynamic>
            : (body as Map<String, dynamic>);
        twin = DigitalTwinRecord.fromJson(twinJson);
      }

      // Combine data
      return {
        'patient_id': id,
        'smpl_data': twinJson,
        'biomarkers': twin?.biomarkers ?? {},
        'last_updated': DateTime.now().toIso8601String(),
        'data_sources': {
          'smpl': twin != null,
          'biomarkers': (twin?.biomarkers ?? {}).isNotEmpty,
        }
      };
    } catch (e) {
      throw Exception('Get live twin data failed: $e');
    }
  }

  /// Update biomarkers by upserting twin only
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
