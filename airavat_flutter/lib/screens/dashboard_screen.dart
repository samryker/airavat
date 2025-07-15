// lib/screens/dashboard_screen.dart
import 'package:flutter/material.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:file_picker/file_picker.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:go_router/go_router.dart';
import 'dart:ui' as ui;
import 'dart:html' as html;
import '../services/api_service.dart';
import '../services/twin_service.dart';
import '../widgets/webgl_twin_widget.dart';

class DashboardScreen extends StatefulWidget {
  @override
  _DashboardScreenState createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  List<PlatformFile> _files = [];
  List<Map<String, String>> _messages = [];
  final TextEditingController _controller = TextEditingController();
  final FocusNode _textFieldFocusNode = FocusNode();
  bool _sending = false;
  String? _currentUserId;
  Map<String, dynamic>? _userBiomarkers;
  String? _userModelUrl;
  bool _isChatOpen = false;

  @override
  void initState() {
    super.initState();
    _loadUserData();

    // Add listener to focus node for debugging
    _textFieldFocusNode.addListener(() {
      print('Focus changed: ${_textFieldFocusNode.hasFocus}');
    });

    // Add a test message to verify chat is working
    WidgetsBinding.instance.addPostFrameCallback((_) {
      setState(() {
        _messages.add({
          'sender': 'bot',
          'text': 'Chat system initialized. Click the input field to test.',
        });
      });
    });
  }

  @override
  void dispose() {
    _textFieldFocusNode.dispose();
    _controller.dispose();
    super.dispose();
  }

  Future<void> _loadUserData() async {
    final user = FirebaseAuth.instance.currentUser;
    if (user != null) {
      setState(() {
        _currentUserId = user.uid;
      });

      // Test API connection
      try {
        final isConnected = await ApiService.testConnection();
        print('API connection test: $isConnected');
        if (!isConnected) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Warning: Cannot connect to AI service'),
              backgroundColor: Colors.orange,
              duration: Duration(seconds: 3),
            ),
          );
        }
      } catch (e) {
        print('API connection test failed: $e');
      }

      // Load user biomarkers and twin customization
      try {
        final biomarkers = await TwinService.getLatestBiomarkers(user.uid);
        final twinCustomization =
            await TwinService.getTwinCustomization(user.uid);

        if (biomarkers != null) {
          setState(() {
            _userBiomarkers = biomarkers;
          });
        }

        // Get modelUrl from twinCustomization
        String? modelUrl =
            twinCustomization != null && twinCustomization['modelUrl'] != null
                ? twinCustomization['modelUrl'] as String
                : null;
        setState(() {
          _userModelUrl = modelUrl;
        });

        // Create default twin if none exists
        if (twinCustomization == null) {
          await TwinService.createDefaultTwin(user.uid);
        }
      } catch (e) {
        print('Error loading user data: $e');
      }
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
    print('Attempting to send message: "$text"');
    print('Controller text: "${_controller.text}"');
    print('Text field focus: ${_textFieldFocusNode.hasFocus}');
    if (text.isEmpty) {
      print('Message is empty, returning');
      return;
    }

    setState(() {
      _messages.add({'sender': 'user', 'text': text});
      _sending = true;
      _controller.clear();
    });

    try {
      print('Calling API service...');
      // Call the deployed FastAPI server
      final response = await ApiService.sendQuery(queryText: text);
      print('API response received: $response');

      setState(() {
        _messages.add({
          'sender': 'bot',
          'text': response['response_text'] ??
              'Sorry, I could not generate a response.',
          'request_id': response['request_id'],
        });
        _sending = false;
      });
    } catch (e) {
      print('Error in _sendMessage: $e');
      setState(() {
        _messages.add({
          'sender': 'bot',
          'text': 'Sorry, I encountered an error: ${e.toString()}',
        });
        _sending = false;
      });
    }
  }

  Future<void> _submitFeedback(String requestId, bool outcomeWorks) async {
    if (requestId.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Cannot submit feedback: No request ID available'),
          backgroundColor: Colors.orange,
          duration: Duration(seconds: 2),
        ),
      );
      return;
    }

    try {
      await ApiService.submitFeedback(
        requestId: requestId,
        outcomeWorks: outcomeWorks,
      );

      // Show a brief feedback confirmation
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(outcomeWorks
              ? 'Thank you for your feedback!'
              : 'We\'ll work to improve.'),
          duration: Duration(seconds: 2),
        ),
      );
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Failed to submit feedback: ${e.toString()}'),
          backgroundColor: Colors.red,
          duration: Duration(seconds: 3),
        ),
      );
    }
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
    final screenSize = MediaQuery.of(context).size;
    final isMobile = screenSize.width < 768;

    return Scaffold(
      appBar: AppBar(
        title: Text('Airavat Digital Twin',
            style: textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.bold, fontFamily: 'sans-serif')),
        centerTitle: true,
        elevation: 1,
        backgroundColor: theme.colorScheme.surface,
        actions: [
          IconButton(
            icon: Container(
              padding: EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: Color(0xFFF1F5F9),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Icon(
                Icons.account_circle_outlined,
                color: Color(0xFF64748B),
                size: 20,
              ),
            ),
            tooltip: 'Account',
            onPressed: () => context.go('/account'),
          ),
          IconButton(
            icon: Container(
              padding: EdgeInsets.all(8),
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: [Color(0xFF3B82F6), Color(0xFF1D4ED8)],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
                borderRadius: BorderRadius.circular(10),
                boxShadow: [
                  BoxShadow(
                    color: Color(0xFF3B82F6).withOpacity(0.3),
                    blurRadius: 8,
                    offset: Offset(0, 2),
                  ),
                ],
              ),
              child: Icon(
                Icons.chat_bubble_outline,
                color: Colors.white,
                size: 20,
              ),
            ),
            tooltip: 'Chat with AI',
            onPressed: () => context.go('/chat'),
          ),
          IconButton(
            icon: Container(
              padding: EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: Color(0xFFF1F5F9),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Icon(
                Icons.upload_file_outlined,
                color: Color(0xFF64748B),
                size: 20,
              ),
            ),
            tooltip: 'Upload Reports',
            onPressed: _pickFiles,
          ),
          IconButton(
            icon: Container(
              padding: EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: Color(0xFFF1F5F9),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Icon(
                Icons.logout_outlined,
                color: Color(0xFF64748B),
                size: 20,
              ),
            ),
            tooltip: 'Log Out',
            onPressed: _logout,
          ),
        ],
      ),
      backgroundColor: theme.colorScheme.background,
      body: Stack(
        children: [
          // Main 3D Twin Section - Centered
          Center(
            child: Container(
              width:
                  isMobile ? screenSize.width * 0.98 : screenSize.width * 0.85,
              height: isMobile
                  ? screenSize.height * 0.75
                  : screenSize.height * 0.85,
              margin: EdgeInsets.all(isMobile ? 4.0 : 20.0),
              child: Card(
                elevation: 12,
                shadowColor: theme.primaryColor.withOpacity(0.4),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(24),
                ),
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(24),
                  child: Container(
                    decoration: BoxDecoration(
                      gradient: LinearGradient(
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                        colors: [
                          theme.colorScheme.surface,
                          theme.colorScheme.surface.withOpacity(0.8),
                        ],
                      ),
                    ),
                    child: Column(
                      children: [
                        // Header
                        Container(
                          padding: EdgeInsets.all(20),
                          decoration: BoxDecoration(
                            gradient: LinearGradient(
                              begin: Alignment.topLeft,
                              end: Alignment.bottomRight,
                              colors: [
                                theme.primaryColor.withOpacity(0.15),
                                theme.primaryColor.withOpacity(0.08),
                              ],
                            ),
                            borderRadius: BorderRadius.only(
                              topLeft: Radius.circular(24),
                              topRight: Radius.circular(24),
                            ),
                            border: Border(
                              bottom: BorderSide(
                                color: theme.primaryColor.withOpacity(0.2),
                                width: 1,
                              ),
                            ),
                          ),
                          child: Row(
                            children: [
                              Icon(
                                Icons.view_in_ar,
                                color: theme.primaryColor,
                                size: 24,
                              ),
                              SizedBox(width: 12),
                              Text(
                                'Your 3D Digital Twin',
                                style: textTheme.titleMedium?.copyWith(
                                  fontWeight: FontWeight.bold,
                                  color: theme.primaryColor,
                                ),
                              ),
                              Spacer(),
                              if (_currentUserId != null)
                                Container(
                                  padding: EdgeInsets.symmetric(
                                      horizontal: 8, vertical: 4),
                                  decoration: BoxDecoration(
                                    color: theme.primaryColor.withOpacity(0.2),
                                    borderRadius: BorderRadius.circular(12),
                                  ),
                                  child: Text(
                                    'ID: ${_currentUserId!.substring(0, 8)}...',
                                    style: textTheme.bodySmall?.copyWith(
                                      color: theme.primaryColor,
                                      fontWeight: FontWeight.w500,
                                    ),
                                  ),
                                ),
                            ],
                          ),
                        ),
                        // 3D Viewer
                        Expanded(
                          child: WebGLTwinWidget(
                            userId: _currentUserId,
                            userBiomarkers: _userBiomarkers,
                            modelUrl: _userModelUrl ?? '/models/male.obj',
                            onOrganSelected: (organ) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                SnackBar(
                                  content: Text('Selected organ: $organ'),
                                  duration: Duration(seconds: 2),
                                ),
                              );
                            },
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),

          // Floating Chat Bubble - Ensure it's on top
          Positioned(
            bottom: isMobile ? 20 : 40,
            right: isMobile ? 20 : 40,
            child: Material(
              elevation: 0,
              color: Colors.transparent,
              child: Column(
                children: [
                  // Chat Messages (when open)
                  if (_isChatOpen)
                    Container(
                      width: isMobile ? screenSize.width * 0.85 : 400,
                      height: 400,
                      margin: EdgeInsets.only(bottom: 16),
                      child: Card(
                        elevation: 12,
                        shadowColor: Colors.black26,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(20),
                        ),
                        child: Column(
                          children: [
                            // Chat Header
                            Container(
                              padding: EdgeInsets.all(16),
                              decoration: BoxDecoration(
                                color: theme.primaryColor,
                                borderRadius: BorderRadius.only(
                                  topLeft: Radius.circular(20),
                                  topRight: Radius.circular(20),
                                ),
                              ),
                              child: Row(
                                children: [
                                  Icon(Icons.smart_toy, color: Colors.white),
                                  SizedBox(width: 8),
                                  Text(
                                    'AI Medical Assistant',
                                    style: TextStyle(
                                      color: Colors.white,
                                      fontWeight: FontWeight.bold,
                                    ),
                                  ),
                                  Spacer(),
                                  IconButton(
                                    icon:
                                        Icon(Icons.close, color: Colors.white),
                                    onPressed: () =>
                                        setState(() => _isChatOpen = false),
                                  ),
                                  IconButton(
                                    icon: Icon(Icons.bug_report,
                                        color: Colors.white),
                                    onPressed: () async {
                                      // Test the chat functionality
                                      setState(() {
                                        _messages.add({
                                          'sender': 'user',
                                          'text': 'Test message'
                                        });
                                        _sending = true;
                                      });

                                      try {
                                        final response = await ApiService.sendQuery(
                                            queryText:
                                                'Hello, this is a test message');
                                        setState(() {
                                          _messages.add({
                                            'sender': 'bot',
                                            'text': response['response_text'] ??
                                                'Test response received',
                                            'request_id':
                                                response['request_id'],
                                          });
                                          _sending = false;
                                        });
                                      } catch (e) {
                                        setState(() {
                                          _messages.add({
                                            'sender': 'bot',
                                            'text':
                                                'Test failed: ${e.toString()}',
                                          });
                                          _sending = false;
                                        });
                                      }
                                    },
                                    tooltip: 'Test Chat',
                                  ),
                                  IconButton(
                                    icon: Icon(Icons.keyboard,
                                        color: Colors.white),
                                    onPressed: () {
                                      // Test text field focus
                                      _textFieldFocusNode.requestFocus();
                                      _controller.text = 'Test text';
                                      setState(() {});
                                    },
                                    tooltip: 'Test Text Field',
                                  ),
                                ],
                              ),
                            ),
                            // Messages
                            Expanded(
                              child: Column(
                                children: [
                                  // Debug info
                                  Container(
                                    padding: EdgeInsets.all(8),
                                    margin: EdgeInsets.all(8),
                                    decoration: BoxDecoration(
                                      color: Colors.orange.shade100,
                                      borderRadius: BorderRadius.circular(8),
                                      border: Border.all(
                                          color: Colors.orange.shade300),
                                    ),
                                    child: Text(
                                      'Debug: Focus=${_textFieldFocusNode.hasFocus}, '
                                      'Text="${_controller.text}", '
                                      'Sending=$_sending',
                                      style: TextStyle(
                                        fontSize: 12,
                                        color: Colors.orange.shade800,
                                      ),
                                    ),
                                  ),
                                  // Messages list
                                  Expanded(
                                    child: ListView.builder(
                                      padding: EdgeInsets.all(12),
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
                                                vertical: 4),
                                            padding: EdgeInsets.symmetric(
                                                horizontal: 12, vertical: 8),
                                            decoration: BoxDecoration(
                                              color: isUser
                                                  ? theme.primaryColor
                                                  : Colors.grey.shade200,
                                              borderRadius:
                                                  BorderRadius.circular(16),
                                            ),
                                            child: Text(
                                              msg['text'] ?? '',
                                              style: TextStyle(
                                                color: isUser
                                                    ? Colors.white
                                                    : Colors.black87,
                                                fontSize: 14,
                                              ),
                                            ),
                                          ),
                                        );
                                      },
                                    ),
                                  ),
                                ],
                              ),
                            ),
                            // Input - Simplified and more reliable
                            Container(
                              padding: EdgeInsets.all(12),
                              child: Row(
                                children: [
                                  Expanded(
                                    child: TextField(
                                      controller: _controller,
                                      focusNode: _textFieldFocusNode,
                                      enabled: !_sending,
                                      keyboardType: TextInputType.text,
                                      textInputAction: TextInputAction.send,
                                      maxLines: 1,
                                      autofocus: false,
                                      decoration: InputDecoration(
                                        hintText: 'Ask your AI twin...',
                                        hintStyle: TextStyle(
                                          color: Colors.grey.shade500,
                                          fontSize: 14,
                                        ),
                                        border: OutlineInputBorder(
                                          borderRadius:
                                              BorderRadius.circular(20),
                                          borderSide: BorderSide(
                                            color: Colors.grey.shade300,
                                            width: 1,
                                          ),
                                        ),
                                        enabledBorder: OutlineInputBorder(
                                          borderRadius:
                                              BorderRadius.circular(20),
                                          borderSide: BorderSide(
                                            color: Colors.grey.shade300,
                                            width: 1,
                                          ),
                                        ),
                                        focusedBorder: OutlineInputBorder(
                                          borderRadius:
                                              BorderRadius.circular(20),
                                          borderSide: BorderSide(
                                            color: theme.primaryColor,
                                            width: 2,
                                          ),
                                        ),
                                        filled: true,
                                        fillColor: Colors.white,
                                        contentPadding: EdgeInsets.symmetric(
                                            horizontal: 16, vertical: 12),
                                        suffixIcon: _sending
                                            ? Padding(
                                                padding: EdgeInsets.all(8.0),
                                                child: SizedBox(
                                                  width: 16,
                                                  height: 16,
                                                  child:
                                                      CircularProgressIndicator(
                                                          strokeWidth: 2,
                                                          color: theme
                                                              .primaryColor),
                                                ),
                                              )
                                            : null,
                                      ),
                                      onSubmitted: _sending
                                          ? null
                                          : (_) => _sendMessage(),
                                      onChanged: (value) {
                                        print(
                                            'TextField text changed: "$value"');
                                        setState(() {});
                                      },
                                      onTap: () {
                                        print('TextField tapped');
                                        if (!_sending) {
                                          _textFieldFocusNode.requestFocus();
                                        }
                                      },
                                      style: TextStyle(
                                        fontSize: 14,
                                        color: Colors.black87,
                                      ),
                                    ),
                                  ),
                                  SizedBox(width: 8),
                                  Container(
                                    decoration: BoxDecoration(
                                      color: _sending
                                          ? Colors.grey.shade300
                                          : theme.primaryColor,
                                      borderRadius: BorderRadius.circular(20),
                                    ),
                                    child: IconButton(
                                      icon: _sending
                                          ? SizedBox(
                                              width: 20,
                                              height: 20,
                                              child: CircularProgressIndicator(
                                                  strokeWidth: 2,
                                                  color: Colors.white),
                                            )
                                          : Icon(Icons.send,
                                              color: Colors.white),
                                      onPressed: _sending ? null : _sendMessage,
                                      tooltip: 'Send message',
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  // Chat Toggle Button
                  FloatingActionButton(
                    onPressed: () {
                      setState(() {
                        _isChatOpen = !_isChatOpen;
                        if (_isChatOpen && _messages.isEmpty) {
                          // Add a welcome message when chat opens for the first time
                          _messages.add({
                            'sender': 'bot',
                            'text':
                                'Hello! I\'m your AI medical assistant. How can I help you today?',
                          });
                        }
                      });
                    },
                    backgroundColor: theme.primaryColor,
                    child: Icon(
                      _isChatOpen ? Icons.close : Icons.chat,
                      color: Colors.white,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
      floatingActionButton: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            colors: [Color(0xFF3B82F6), Color(0xFF1D4ED8)],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          borderRadius: BorderRadius.circular(16),
          boxShadow: [
            BoxShadow(
              color: Color(0xFF3B82F6).withOpacity(0.4),
              blurRadius: 12,
              offset: Offset(0, 6),
            ),
          ],
        ),
        child: Material(
          color: Colors.transparent,
          child: InkWell(
            borderRadius: BorderRadius.circular(16),
            onTap: () => context.go('/chat'),
            child: Container(
              padding: EdgeInsets.symmetric(horizontal: 20, vertical: 12),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(
                    Icons.chat_bubble_outline,
                    color: Colors.white,
                    size: 20,
                  ),
                  SizedBox(width: 8),
                  Text(
                    'Chat with AI',
                    style: TextStyle(
                      color: Colors.white,
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ],
              ),
            ),
          ),
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
