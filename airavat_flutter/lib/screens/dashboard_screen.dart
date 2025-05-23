// lib/screens/dashboard_screen.dart
import 'package:flutter/material.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:file_picker/file_picker.dart';
// import 'package:fl_chart/fl_chart.dart'; // Not used in the provided code, consider removing if not needed
// import 'package:lottie/lottie.dart'; // Not used, consider removing
import 'package:firebase_auth/firebase_auth.dart';
import 'package:go_router/go_router.dart';
import 'dart:ui' as ui;
import 'dart:html' as html; // Be cautious with dart:html for cross-platform

class DashboardScreen extends StatefulWidget {
  @override
  _DashboardScreenState createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  final String _viewId = 'threejs-viewer';
  List<PlatformFile> _files = [];
  // bool _uploading = false; // Not used currently
  List<Map<String, String>> _messages = [];
  final TextEditingController _controller = TextEditingController();
  bool _sending = false;

  @override
  void initState() {
    super.initState();
    // Conditional registration for web
    // ignore: unnecessary_null_comparison
    if (html.window != null) {
      // Check if running on web
      // ignore: undefined_prefixed_name
      ui.platformViewRegistry.registerViewFactory(
        _viewId,
        (int viewId) {
          final html.IFrameElement iframe = html.IFrameElement()
            ..src =
                'viewer/index.html' // Make sure this path is correct relative to your web build
            ..style.border = 'none'
            ..style.width = '100%'
            ..style.height = '100%';
          return iframe;
        },
      );
    }
  }

  Future<void> _logout() async {
    await FirebaseAuth.instance.signOut();
    if (!mounted) return;
    context.go('/login');
  }

  Future<void> _pickFiles() async {
    final result = await FilePicker.platform.pickFiles(allowMultiple: true);
    if (result != null) setState(() => _files = result.files);
  }

  Future<void> _sendMessage() async {
    final text = _controller.text.trim();
    if (text.isEmpty) return;
    setState(() {
      _messages.add({'sender': 'user', 'text': text});
      _sending = true;
      _controller.clear();
    });
    // Simulate API call
    await Future.delayed(Duration(seconds: 1));
    setState(() {
      _messages.add({
        'sender': 'bot',
        'text': 'This is a placeholder AI response. Agent integration pending.'
      });
      _sending = false;
    });
  }

  InputDecoration _inputDecoration(String labelText,
      {String? hintText, IconData? prefixIcon}) {
    return InputDecoration(
      labelText: labelText,
      hintText: hintText,
      prefixIcon: prefixIcon != null
          ? Icon(prefixIcon,
              color: Theme.of(context).primaryColor.withOpacity(0.7))
          : null,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: BorderSide(color: Colors.grey.shade300),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: BorderSide(color: Colors.grey.shade300),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide:
            BorderSide(color: Theme.of(context).primaryColor, width: 1.5),
      ),
      filled: true,
      fillColor: Colors.grey[50],
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final textTheme = theme.textTheme;

    return Scaffold(
      appBar: AppBar(
        title: Text('Airavat Dashboard',
            style: textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.bold, fontFamily: 'sans-serif')),
        centerTitle: true,
        elevation: 1,
        actions: [
          IconButton(
            icon: Icon(Icons.account_circle_outlined),
            tooltip: 'Account',
            onPressed: () => context.go('/account'),
          ),
          IconButton(
            icon: Icon(Icons.upload_file_outlined),
            tooltip: 'Upload Reports',
            onPressed: _pickFiles,
          ),
          IconButton(
            icon: Icon(Icons.logout_outlined),
            tooltip: 'Log Out',
            onPressed: _logout,
          ),
        ],
      ),
      backgroundColor: theme.colorScheme
          .background, // Or Colors.grey[100] for a slightly off-white bg
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // 3D Viewer Section
            _buildSectionTitle('3D Digital Twin', textTheme, theme),
            Card(
              shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12)),
              clipBehavior: Clip.antiAlias,
              elevation: 3,
              child: SizedBox(
                height: 280, // You can adjust this height
                // Conditional child for web vs. mobile for the 3D viewer
                child: (html.window !=
                        null) // Simplified condition to check for web
                    ? HtmlElementView(viewType: _viewId)
                    : Center(
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(Icons.view_in_ar_outlined,
                                size: 48, color: Colors.grey.shade400),
                            const SizedBox(height: 8),
                            Text(
                              '3D Digital Twin Viewer available on Web',
                              textAlign: TextAlign.center,
                              style: textTheme.bodyMedium?.copyWith(
                                  color: Colors.grey.shade600,
                                  fontFamily: 'sans-serif'),
                            ),
                          ],
                        ),
                      ),
              ),
            ),
            const SizedBox(height: 24),

            // Chat / Query Section
            _buildSectionTitle('Ask your AI Twin', textTheme, theme),
            Card(
              elevation: 3,
              shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12)),
              color: theme.brightness == Brightness.light
                  ? Colors.white
                  : Colors.grey.shade800, // Explicit card color
              margin: const EdgeInsets.only(
                  bottom: 16), // Add some bottom margin if needed
              child: Container(
                height: 380, // Increased height slightly for better spacing
                child: Column(
                  children: [
                    Expanded(
                      child: ListView.builder(
                        padding:
                            const EdgeInsets.all(12.0), // Increased padding
                        itemCount: _messages.length,
                        itemBuilder: (context, i) {
                          final msg = _messages[i];
                          final isUser = msg['sender'] == 'user';
                          return Align(
                            alignment: isUser
                                ? Alignment.centerRight
                                : Alignment.centerLeft,
                            child: Container(
                              margin: const EdgeInsets.symmetric(
                                  vertical: 6, horizontal: 8),
                              padding: const EdgeInsets.symmetric(
                                  vertical: 12, horizontal: 16),
                              decoration: BoxDecoration(
                                color: isUser
                                    ? theme
                                        .primaryColor // Solid primary color for user
                                    : (theme.brightness == Brightness.light
                                        ? Colors.grey.shade200
                                        : Colors.grey.shade700),
                                borderRadius: BorderRadius.circular(18),
                              ),
                              child: Text(
                                msg['text'] ?? '',
                                style: textTheme.bodyMedium?.copyWith(
                                  fontFamily: 'sans-serif',
                                  color: isUser
                                      ? Colors.white
                                      : (theme.brightness == Brightness.light
                                          ? Colors.black87
                                          : Colors.white70),
                                ),
                              ),
                            ),
                          );
                        },
                      ),
                    ),
                    Divider(
                        height: 1, thickness: 1, color: Colors.grey.shade300),
                    Padding(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 8.0,
                          vertical: 8.0), // Added vertical padding
                      child: Row(
                        children: [
                          Expanded(
                            child: TextField(
                              controller: _controller,
                              style: textTheme.bodyMedium
                                  ?.copyWith(fontFamily: 'sans-serif'),
                              decoration: InputDecoration(
                                hintText: 'Ask a question to your twin...',
                                border: InputBorder.none,
                                filled: true, // Fill the text field background
                                fillColor: theme.brightness == Brightness.light
                                    ? Colors.grey.shade100
                                    : Colors.grey.shade700, // Subtle fill
                                contentPadding: const EdgeInsets.symmetric(
                                    horizontal: 16, vertical: 14),
                                hintStyle: textTheme.bodyMedium?.copyWith(
                                    color: Colors.grey.shade500,
                                    fontFamily: 'sans-serif'),
                              ),
                              onSubmitted:
                                  _sending ? null : (_) => _sendMessage(),
                            ),
                          ),
                          const SizedBox(width: 8),
                          IconButton(
                              icon: _sending
                                  ? SizedBox(
                                      width: 22,
                                      height: 22,
                                      child: CircularProgressIndicator(
                                          strokeWidth: 2.5,
                                          color: theme.primaryColor),
                                    )
                                  : Icon(Icons.send_rounded,
                                      color: theme.primaryColor, size: 28),
                              tooltip: 'Send Message',
                              onPressed: _sending ? null : _sendMessage,
                              style: IconButton.styleFrom(
                                  // Add some style to the button for better touch target
                                  padding: const EdgeInsets.all(12),
                                  backgroundColor:
                                      theme.primaryColor.withOpacity(0.1),
                                  shape: RoundedRectangleBorder(
                                      borderRadius:
                                          BorderRadius.circular(12)))),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 24),

            // Uploaded Files Preview Section
            if (_files.isNotEmpty) ...[
              _buildSectionTitle('Selected Reports', textTheme, theme),
              Card(
                elevation: 3,
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12)),
                child: Padding(
                  padding: EdgeInsets.symmetric(vertical: 8.0),
                  child: Column(
                    children: List<Widget>.from(_files.map((f) => ListTile(
                          leading: Icon(Icons.description_outlined,
                              color: theme.primaryColor),
                          title: Text(f.name,
                              style: textTheme.bodyMedium?.copyWith(
                                  fontFamily: 'sans-serif',
                                  fontWeight: FontWeight.w500)),
                          subtitle: Text(
                              '${(f.size / 1024).toStringAsFixed(2)} KB',
                              style: textTheme.bodySmall?.copyWith(
                                  fontFamily: 'sans-serif',
                                  color: Colors.grey.shade600)),
                          trailing: IconButton(
                            icon: Icon(Icons.clear,
                                color: Colors.grey.shade500, size: 20),
                            tooltip: 'Remove File',
                            onPressed: () {
                              setState(() {
                                _files.remove(f);
                              });
                            },
                          ),
                        ))),
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildSectionTitle(
      String title, TextTheme textTheme, ThemeData theme) {
    return Padding(
      padding: EdgeInsets.only(top: 8.0, bottom: 12.0),
      child: Text(
        title,
        style: textTheme.headlineSmall?.copyWith(
            fontWeight: FontWeight.w600,
            fontFamily: 'sans-serif',
            color: theme.primaryColorDark),
      ),
    );
  }
}
