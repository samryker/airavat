// lib/screens/dashboard_screen.dart
import 'package:flutter/material.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:file_picker/file_picker.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:lottie/lottie.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:go_router/go_router.dart';
import 'dart:ui' as ui;
import 'dart:html' as html;

class DashboardScreen extends StatefulWidget {
  @override
  _DashboardScreenState createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  final String _viewId = 'threejs-viewer';
  List<PlatformFile> _files = [];
  bool _uploading = false;
  List<Map<String, String>> _messages = [];
  final TextEditingController _controller = TextEditingController();
  bool _sending = false;

  @override
  void initState() {
    super.initState();
    // Register the Three.js viewer iframe
    // ignore: undefined_prefixed_name
    ui.platformViewRegistry.registerViewFactory(
      _viewId,
      (int viewId) {
        final html.IFrameElement iframe = html.IFrameElement()
          ..src = 'viewer/index.html'
          ..style.border = 'none'
          ..width = '100%'
          ..height = '100%';
        return iframe;
      },
    );
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
    // TODO: call your Agent API endpoint
    await Future.delayed(Duration(seconds: 1));
    setState(() {
      _messages
          .add({'sender': 'bot', 'text': 'This is a placeholder response.'});
      _sending = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        title: Text('Dashboard', style: TextStyle(fontWeight: FontWeight.bold)),
        actions: [
          IconButton(
            icon: Icon(Icons.account_circle),
            tooltip: 'Account',
            onPressed: () => context.go('/account'),
          ),
          IconButton(
            icon: Icon(Icons.upload_file),
            tooltip: 'Upload Reports',
            onPressed: _pickFiles,
          ),
          IconButton(
            icon: Icon(Icons.logout),
            tooltip: 'Log Out',
            onPressed: _logout,
          ),
        ],
      ),
      backgroundColor: theme.colorScheme.background,
      body: SingleChildScrollView(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // 3D Viewer
              Text('3D Digital Twin', style: theme.textTheme.headline6),
              SizedBox(height: 8),
              Card(
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12)),
                clipBehavior: Clip.antiAlias,
                elevation: 3,
                child: SizedBox(
                  height: 250,
                  child: HtmlElementView(viewType: _viewId),
                ),
              ),
              SizedBox(height: 24),
              // Chat / Query
              Text('Ask your AI Twin', style: theme.textTheme.headline6),
              SizedBox(height: 8),
              Container(
                height: 300,
                decoration: BoxDecoration(
                  border: Border.all(color: Colors.grey.shade300),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Column(
                  children: [
                    Expanded(
                      child: ListView.builder(
                        itemCount: _messages.length,
                        itemBuilder: (context, i) {
                          final msg = _messages[i];
                          final isUser = msg['sender'] == 'user';
                          return Align(
                            alignment: isUser
                                ? Alignment.centerRight
                                : Alignment.centerLeft,
                            child: Container(
                              margin: EdgeInsets.symmetric(
                                  vertical: 4, horizontal: 8),
                              padding: EdgeInsets.all(12),
                              decoration: BoxDecoration(
                                color: isUser
                                    ? theme.colorScheme.primary.withOpacity(0.1)
                                    : Colors.grey.shade100,
                                borderRadius: BorderRadius.circular(8),
                              ),
                              child: Text(msg['text'] ?? ''),
                            ),
                          );
                        },
                      ),
                    ),
                    Divider(height: 1),
                    Row(
                      children: [
                        Expanded(
                          child: TextField(
                            controller: _controller,
                            decoration: InputDecoration(
                              hintText: 'Ask a question...',
                              border: InputBorder.none,
                              contentPadding: EdgeInsets.all(12),
                            ),
                            onSubmitted: (_) => _sendMessage(),
                          ),
                        ),
                        IconButton(
                          icon: _sending
                              ? SizedBox(
                                  width: 24,
                                  height: 24,
                                  child:
                                      CircularProgressIndicator(strokeWidth: 2),
                                )
                              : Icon(Icons.send,
                                  color: theme.colorScheme.primary),
                          onPressed: _sending ? null : _sendMessage,
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              SizedBox(height: 24),
              // Uploaded Files Preview
              if (_files.isNotEmpty) ...[
                Text('Selected Reports:', style: theme.textTheme.headline6),
                SizedBox(height: 8),
                ..._files.map((f) => ListTile(
                      leading: Icon(Icons.insert_drive_file,
                          color: theme.colorScheme.primary),
                      title: Text(f.name),
                      subtitle:
                          Text('${(f.size / 1024).toStringAsFixed(2)} KB'),
                    )),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
