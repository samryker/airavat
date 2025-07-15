import 'package:flutter/material.dart';
import 'dart:ui' as ui;
import 'dart:html' as html;

class WebGLTwinWidget extends StatefulWidget {
  final String? userId;
  final Map<String, dynamic>? userBiomarkers;
  final Function(String)? onOrganSelected;
  final String? modelUrl;

  const WebGLTwinWidget({
    Key? key,
    this.userId,
    this.userBiomarkers,
    this.onOrganSelected,
    this.modelUrl,
  }) : super(key: key);

  @override
  _WebGLTwinWidgetState createState() => _WebGLTwinWidgetState();
}

class _WebGLTwinWidgetState extends State<WebGLTwinWidget> {
  final String _viewId =
      'threejs-viewer-${DateTime.now().millisecondsSinceEpoch}';
  bool _isWeb = false;

  @override
  void initState() {
    super.initState();
    _initializeWebView();
  }

  void _initializeWebView() {
    // Check if running on web
    try {
      // ignore: unnecessary_null_comparison
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
        final url = widget.modelUrl ?? '/models/male.obj';
        final html.IFrameElement iframe = html.IFrameElement()
          ..src = '/viewer/index.html?modelUrl=$url'
          ..style.border = 'none'
          ..style.width = '100%'
          ..style.height = '100%'
          ..style.borderRadius = '12px'
          ..style.boxShadow = '0 8px 32px rgba(0, 0, 0, 0.3)'
          ..allow =
              'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture'
          ..allowFullscreen = true;

        // Add message listener for communication between Flutter and 3D viewer
        html.window.addEventListener('message', (event) {
          final messageEvent = event as html.MessageEvent;
          if (messageEvent.data is Map &&
              messageEvent.data['type'] == 'organSelected') {
            widget.onOrganSelected?.call(messageEvent.data['organ']);
          }
        });

        return iframe;
      },
    );
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

            // Overlay for better visual integration
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

            // Loading indicator
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
              SizedBox(height: 16),
              if (widget.userId != null)
                Container(
                  padding: EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  decoration: BoxDecoration(
                    color: theme.primaryColor.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(
                      color: theme.primaryColor.withOpacity(0.3),
                    ),
                  ),
                  child: Text(
                    'User ID: ${widget.userId!.substring(0, 8)}...',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: theme.primaryColor,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                ),
              SizedBox(height: 24),
              Container(
                padding: EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: theme.colorScheme.surface,
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(
                    color: theme.colorScheme.outline.withOpacity(0.2),
                  ),
                ),
                child: Column(
                  children: [
                    Icon(
                      Icons.info_outline,
                      color: theme.colorScheme.primary,
                      size: 20,
                    ),
                    SizedBox(height: 8),
                    Text(
                      'Open in web browser for full 3D experience',
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.onSurface.withOpacity(0.6),
                      ),
                      textAlign: TextAlign.center,
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// Helper class for 3D twin customization
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
