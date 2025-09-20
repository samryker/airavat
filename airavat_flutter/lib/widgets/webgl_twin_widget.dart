import 'package:flutter/material.dart';
import 'dart:ui' as ui;
import 'dart:html' as html;
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';
import '../services/digital_twin_service.dart';

class WebGLTwinWidget extends StatefulWidget {
  final String? userId;
  final Map<String, dynamic>? userBiomarkers;
  final Function(String)? onOrganSelected;
  final String? modelUrl;
  // New optional initial parameters to sync with the viewer
  final String? initialGender; // 'male' | 'female' | 'neutral'
  final double? initialHeightCm; // e.g., 170
  final double? initialWeightKg; // e.g., 70
  final double? initialBeta1; // 0..1

  const WebGLTwinWidget({
    Key? key,
    this.userId,
    this.userBiomarkers,
    this.onOrganSelected,
    this.modelUrl,
    this.initialGender,
    this.initialHeightCm,
    this.initialWeightKg,
    this.initialBeta1,
  }) : super(key: key);

  @override
  _WebGLTwinWidgetState createState() => _WebGLTwinWidgetState();
}

class _WebGLTwinWidgetState extends State<WebGLTwinWidget> {
  final String _viewId =
      'threejs-viewer-${DateTime.now().millisecondsSinceEpoch}';
  bool _isWeb = false;
  html.IFrameElement? _iframeRef;

  @override
  void initState() {
    super.initState();
    _initializeWebView();
  }

  @override
  void didUpdateWidget(covariant WebGLTwinWidget oldWidget) {
    super.didUpdateWidget(oldWidget);
    // If initial parameters change, push update to iframe
    _postSmplUpdate(
      gender: widget.initialGender,
      height: widget.initialHeightCm,
      weight: widget.initialWeightKg,
      beta1: widget.initialBeta1,
    );
  }

  void _initializeWebView() {
    try {
      if (html.window != null) {
        _isWeb = true;
        _registerViewFactory();
      }
    } catch (e) {
      _isWeb = false;
    }
  }

  void _registerViewFactory() {
    // ignore: undefined_prefixed_name
    ui.platformViewRegistry.registerViewFactory(
      _viewId,
      (int viewId) {
        final urlParam =
            (widget.modelUrl != null && widget.modelUrl!.isNotEmpty)
                ? '?modelUrl=${widget.modelUrl}'
                : '';
        final html.IFrameElement iframe = html.IFrameElement()
          ..id = 'airavat-twin-iframe'
          ..src = '/viewer/index.html$urlParam'
          ..style.border = 'none'
          ..style.width = '100%'
          ..style.height = '100%'
          ..style.borderRadius = '12px'
          ..style.boxShadow = '0 8px 32px rgba(0, 0, 0, 0.3)'
          ..allow =
              'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture'
          ..allowFullscreen = true;

        // Store ref for messaging
        _iframeRef = iframe;

        // Post initial parameters once iframe loads
        iframe.onLoad.listen((_) async {
          // Load patient with biomarkers
          await _loadPatientWithBiomarkers();

          // If no initial gender provided, load saved model from Firestore
          if (widget.initialGender == null || widget.initialGender!.isEmpty) {
            await _loadSavedModelAndPost();
          }
        });

        // Listener for communication from viewer
        html.window.addEventListener('message', (event) async {
          final messageEvent = event as html.MessageEvent;
          final data = messageEvent.data;
          if (data is Map && data['type'] == 'organSelected') {
            widget.onOrganSelected?.call(data['organ']);
          }
          if (data is Map && data['type'] == 'smpl:model_changed') {
            final model = (data['model'] as String?)?.toLowerCase();
            if (model == 'male' || model == 'female' || model == 'neutral') {
              await _persistModelSelection(model!);
            }
          }
        });

        return iframe;
      },
    );
  }

  Future<void> _loadSavedModelAndPost() async {
    try {
      final userId = widget.userId ?? FirebaseAuth.instance.currentUser?.uid;
      if (userId == null) return;
      final doc = await FirebaseFirestore.instance
          .collection('patients')
          .doc(userId)
          .get();
      if (doc.exists) {
        final data = doc.data();
        final profile = (data?['profile'] ?? {}) as Map<String, dynamic>;
        final saved = (profile['smpl_model'] ?? data?['smpl_model'])
            ?.toString()
            .toLowerCase();
        final model =
            (saved == 'male' || saved == 'female' || saved == 'neutral')
                ? saved
                : null;
        if (model != null) {
          _postSmplUpdate(gender: model);
        }
      }
    } catch (_) {}
  }

  Future<void> _persistModelSelection(String model) async {
    try {
      final userId = widget.userId ?? FirebaseAuth.instance.currentUser?.uid;
      if (userId == null) return;
      await FirebaseFirestore.instance.collection('patients').doc(userId).set({
        'profile': {'smpl_model': model}
      }, SetOptions(merge: true));
    } catch (_) {}
  }

  Future<void> _loadPatientWithBiomarkers() async {
    if (_iframeRef?.contentWindow == null || widget.userId == null) return;

    try {
      // Get live twin data including biomarkers
      final liveTwinData =
          await DigitalTwinService.getLiveTwinData(patientId: widget.userId);

      final profile = {
        'patientId': widget.userId,
        'height': widget.initialHeightCm ??
            liveTwinData['smpl_data']?['height_cm'] ??
            170.0,
        'weight': widget.initialWeightKg ??
            liveTwinData['smpl_data']?['weight_kg'] ??
            70.0,
        'gender': widget.initialGender ?? 'neutral',
      };

      // Load patient in viewer
      _iframeRef!.contentWindow!.postMessage({
        'type': 'loadPatient',
        'patientId': widget.userId,
        'profile': profile,
      }, '*');

      // Send biomarkers if available
      final biomarkers =
          liveTwinData['biomarkers'] ?? widget.userBiomarkers ?? {};
      if (biomarkers.isNotEmpty) {
        _iframeRef!.contentWindow!.postMessage({
          'type': 'updateBiomarkers',
          'biomarkers': biomarkers,
        }, '*');
      }

      print(
          '✅ Loaded patient ${widget.userId} with ${biomarkers.length} biomarkers');
    } catch (e) {
      print('Error loading patient biomarkers: $e');
      // Fallback to basic SMPL update
      _postSmplUpdate(
        gender: widget.initialGender,
        height: widget.initialHeightCm,
        weight: widget.initialWeightKg,
        beta1: widget.initialBeta1,
      );
    }
  }

  void _postSmplUpdate({
    String? gender,
    double? height,
    double? weight,
    double? beta1,
  }) {
    if (_iframeRef?.contentWindow == null) return;
    final payload = <String, dynamic>{};
    if (gender != null && gender.isNotEmpty)
      payload['gender'] = gender.toLowerCase();
    if (height != null) payload['height'] = height;
    if (weight != null) payload['weight'] = weight;
    if (beta1 != null) payload['beta1'] = beta1;
    if (payload.isEmpty) return;

    _iframeRef!.contentWindow!.postMessage({
      'type': 'smpl:update',
      'payload': payload,
    }, '*');
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final screenSize = MediaQuery.of(context).size;
    final isMobile = screenSize.width < 768;

    if (!_isWeb) {
      return _buildMobilePlaceholder();
    }

    return Container(
      width: double.infinity,
      height: double.infinity,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(12),
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            theme.colorScheme.surface,
            theme.colorScheme.surface.withOpacity(0.8),
          ],
        ),
        boxShadow: [
          BoxShadow(
            color: theme.primaryColor.withOpacity(0.1),
            blurRadius: 20,
            offset: Offset(0, 8),
          ),
        ],
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(12),
        child: Stack(
          children: [
            // 3D Viewer
            HtmlElementView(viewType: _viewId),

            // Overlay
            Positioned(
              top: 0,
              left: 0,
              right: 0,
              child: Container(
                height: 4,
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: [
                      theme.primaryColor.withOpacity(0.8),
                      theme.primaryColor.withOpacity(0.4),
                      Colors.transparent,
                    ],
                  ),
                ),
              ),
            ),

            if (widget.userId == null)
              Container(
                color: Colors.black.withOpacity(0.7),
                child: Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      CircularProgressIndicator(
                        valueColor:
                            AlwaysStoppedAnimation<Color>(theme.primaryColor),
                      ),
                      SizedBox(height: 16),
                      Text(
                        'Loading your digital twin...',
                        style: TextStyle(
                          color: Colors.white,
                          fontSize: 16,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildMobilePlaceholder() {
    final theme = Theme.of(context);
    final screenSize = MediaQuery.of(context).size;
    final isMobile = screenSize.width < 768;

    return Container(
      width: double.infinity,
      height: double.infinity,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(12),
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            theme.colorScheme.surface,
            theme.colorScheme.surface.withOpacity(0.8),
          ],
        ),
        border: Border.all(
          color: theme.primaryColor.withOpacity(0.2),
          width: 1,
        ),
      ),
      child: Center(
        child: Padding(
          padding: EdgeInsets.all(isMobile ? 20 : 32),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                padding: EdgeInsets.all(20),
                decoration: BoxDecoration(
                  color: theme.primaryColor.withOpacity(0.1),
                  shape: BoxShape.circle,
                ),
                child: Icon(
                  Icons.view_in_ar_outlined,
                  size: isMobile ? 48 : 64,
                  color: theme.primaryColor,
                ),
              ),
              SizedBox(height: 24),
              Text(
                '3D Digital Twin',
                style: theme.textTheme.headlineSmall?.copyWith(
                  fontWeight: FontWeight.bold,
                  color: theme.primaryColor,
                ),
                textAlign: TextAlign.center,
              ),
              SizedBox(height: 12),
              Text(
                'Available on Web Browser',
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: theme.colorScheme.onSurface.withOpacity(0.7),
                  fontFamily: 'sans-serif',
                ),
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class TwinCustomization {
  final String userId;
  final Map<String, dynamic> biomarkers;
  final Map<String, String> organColors;
  final List<String> highlightedOrgans;

  TwinCustomization({
    required this.userId,
    required this.biomarkers,
    this.organColors = const {},
    this.highlightedOrgans = const [],
  });

  Map<String, dynamic> toJson() {
    return {
      'userId': userId,
      'biomarkers': biomarkers,
      'organColors': organColors,
      'highlightedOrgans': highlightedOrgans,
    };
  }

  factory TwinCustomization.fromJson(Map<String, dynamic> json) {
    return TwinCustomization(
      userId: json['userId'] ?? '',
      biomarkers: Map<String, dynamic>.from(json['biomarkers'] ?? {}),
      organColors: Map<String, String>.from(json['organColors'] ?? {}),
      highlightedOrgans: List<String>.from(json['highlightedOrgans'] ?? []),
    );
  }
}
