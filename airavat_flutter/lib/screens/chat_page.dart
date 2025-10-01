import 'package:flutter/material.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:go_router/go_router.dart';
import 'package:file_picker/file_picker.dart';
import '../services/api_service.dart';
import '../widgets/context_history_widget.dart';

class ChatPage extends StatefulWidget {
  @override
  _ChatPageState createState() => _ChatPageState();
}

class _ChatPageState extends State<ChatPage> with TickerProviderStateMixin {
  List<Map<String, String>> _messages = [];
  final TextEditingController _controller = TextEditingController();
  final FocusNode _textFieldFocusNode = FocusNode();
  final ScrollController _scrollController = ScrollController();
  bool _sending = false;
  bool _contextReady = false; // gate send until context is loaded
  String? _currentUserId;
  late AnimationController _fadeController;
  late AnimationController _slideController;
  late Animation<double> _fadeAnimation;
  late Animation<Offset> _slideAnimation;
  Map<String, dynamic>? _patientContext; // Added for patient context
  bool _showContextHistory = true; // Control visibility of context history
  String _contextSummary = ''; // Store context summary for AI

  // Analysis status tracking
  bool _isAnalyzing = false;
  bool _analysisComplete = false;
  late AnimationController _redDotController;
  late Animation<double> _redDotPulseAnimation;
  // String? _lastAnalysisRequestId; // For future use to track specific analysis requests

  // File upload and analysis state
  List<PlatformFile> _uploadedFiles = [];
  Map<String, String> _fileAnalysisResults = {}; // filename -> analysis result
  bool _isUploadingFile = false;

  // Treatment update functionality
  bool _showTreatmentUpdateButton = false;
  String? _latestResponseForTreatment;
  String? _latestRequestId;

  @override
  void initState() {
    super.initState();
    _loadUserData();

    // Initialize animations
    _fadeController = AnimationController(
      duration: const Duration(milliseconds: 800),
      vsync: this,
    );
    _slideController = AnimationController(
      duration: const Duration(milliseconds: 600),
      vsync: this,
    );

    _fadeAnimation = Tween<double>(
      begin: 0.0,
      end: 1.0,
    ).animate(CurvedAnimation(
      parent: _fadeController,
      curve: Curves.easeInOut,
    ));

    _slideAnimation = Tween<Offset>(
      begin: const Offset(0, 0.3),
      end: Offset.zero,
    ).animate(CurvedAnimation(
      parent: _slideController,
      curve: Curves.easeOutCubic,
    ));

    // Initialize red dot animation for analysis indicator
    _redDotController = AnimationController(
      duration: const Duration(milliseconds: 1000),
      vsync: this,
    );
    _redDotPulseAnimation = Tween<double>(
      begin: 0.6,
      end: 1.0,
    ).animate(CurvedAnimation(
      parent: _redDotController,
      curve: Curves.easeInOut,
    ));

    // Add listener to focus node for debugging
    _textFieldFocusNode.addListener(() {
      print('Focus changed: ${_textFieldFocusNode.hasFocus}');
    });

    // Add a welcome message with animation
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _fadeController.forward();
      _slideController.forward();
      setState(() {
        _messages.add({
          'sender': 'bot',
          'text':
              'Hello! I\'m Airavat, your AI medical assistant. I\'m here to help you with health-related questions and provide guidance. How can I assist you today?',
        });
      });
    });
  }

  @override
  void dispose() {
    _textFieldFocusNode.dispose();
    _controller.dispose();
    _scrollController.dispose();
    _fadeController.dispose();
    _slideController.dispose();
    _redDotController.dispose();
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

      // Load conversation history
      try {
        final historyResponse =
            await ApiService.getConversationHistory(limit: 5);
        if (historyResponse['status'] == 'success') {
          final history = historyResponse['conversation_history'] as List;
          print('Loaded ${history.length} previous conversations');

          // Add a personalized welcome message based on history
          if (history.isNotEmpty) {
            setState(() {
              _messages.add({
                'sender': 'bot',
                'text':
                    'Welcome back! I remember our previous conversations. How can I help you today?',
              });
            });
          }
        }
      } catch (e) {
        print('Error loading conversation history: $e');
      }

      // Load patient context for personalized experience
      try {
        final context = await ApiService.getPatientContext();
        if (context != null) {
          print('Loaded patient context (local Firebase)');
          _patientContext = context;
          _contextReady = true;
          setState(() {});
        } else {
          _contextReady = true; // allow chat even if no context
          setState(() {});
        }
      } catch (e) {
        print('Error loading patient context: $e');
        _contextReady = true; // fail-open to allow chat
        setState(() {});
      }
    }
  }

  // Callback when context is loaded
  void _onContextLoaded(String summary) {
    setState(() {
      _contextSummary = summary;
    });
  }

  Future<void> _updateTreatmentInFirebase() async {
    if (_latestResponseForTreatment == null || _currentUserId == null) return;

    try {
      setState(() {
        _isAnalyzing = true;
      });

      final treatmentData = {
        'treatmentName': 'AI Medical Guidance',
        'condition': 'Generated by Gemini AI',
        'treatment_text': _latestResponseForTreatment,
        'timestamp': DateTime.now().toIso8601String(),
        'request_id': _latestRequestId,
        'type': 'gemini_treatment_update',
        'updated_by': 'patient_action',
        'startDate': DateTime.now().toIso8601String(),
        'status': 'active',
        'source': 'ai_assistant',
        'plan_type': 'ai_guidance',
        'priority': 'medium',
      };

      // Update treatment plan via API
      print('Sending treatment data: $treatmentData');
      print('Current user ID: $_currentUserId');

      // Save directly to Firestore patients collection
      final updateResponse =
          await ApiService.updateTreatmentPlan(treatmentData);
      print('Treatment saved to Firestore: $updateResponse');

      if (updateResponse['status'] == 'success') {
        // Add confirmation message to chat
        setState(() {
          _messages.add({
            'sender': 'bot',
            'text':
                '✅ Treatment updated successfully! Your latest medical guidance has been saved to your profile and will be considered in future consultations.',
            'type': 'treatment_confirmation',
          });
          _showTreatmentUpdateButton = false;
          _latestResponseForTreatment = null;
          _latestRequestId = null;
        });

        // Show success snackbar
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Treatment updated successfully!'),
              backgroundColor: Colors.green,
              duration: Duration(seconds: 3),
            ),
          );
        }

        // Scroll to bottom to show confirmation message
        WidgetsBinding.instance.addPostFrameCallback((_) {
          _scrollController.animateTo(
            _scrollController.position.maxScrollExtent,
            duration: const Duration(milliseconds: 300),
            curve: Curves.easeOut,
          );
        });
      } else {
        throw Exception(
            'Failed to update treatment: ${updateResponse['message'] ?? 'Unknown error'}');
      }
    } catch (e) {
      print('Error updating treatment: $e');
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to update treatment: ${e.toString()}'),
            backgroundColor: Colors.red,
            duration: const Duration(seconds: 5),
          ),
        );
      }

      // Also add error message to chat for better debugging
      setState(() {
        _messages.add({
          'sender': 'bot',
          'text':
              '❌ Error saving treatment: ${e.toString()}. Please try again or contact support.',
          'type': 'error_message',
        });
      });
    } finally {
      setState(() {
        _isAnalyzing = false;
      });
    }
  }

  Future<void> _pickAndAnalyzeFile() async {
    try {
      final result = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['pdf', 'doc', 'docx', 'txt', 'jpg', 'jpeg', 'png'],
        allowMultiple: false,
      );

      if (result != null && result.files.isNotEmpty) {
        setState(() {
          _isUploadingFile = true;
        });

        final file = result.files.first;
        print('Selected file: ${file.name}, size: ${file.size}');

        // Analyze file with Gemini
        final analysisResult = await _analyzeFileWithGemini(file);

        setState(() {
          _uploadedFiles.add(file);
          _fileAnalysisResults[file.name] = analysisResult;
          _isUploadingFile = false;
        });

        // Add file upload message to chat
        setState(() {
          _messages.add({
            'sender': 'user',
            'text': '📄 Uploaded: ${file.name}',
            'file_name': file.name,
            'type': 'file_upload',
          });

          _messages.add({
            'sender': 'bot',
            'text':
                'I\'ve analyzed your uploaded file "${file.name}". Here\'s what I found:\n\n$analysisResult\n\nYou can now ask me questions about this document.',
            'request_id':
                'file_analysis_${DateTime.now().millisecondsSinceEpoch}',
            'file_related': 'true',
          });
        });

        // Scroll to bottom
        WidgetsBinding.instance.addPostFrameCallback((_) {
          _scrollController.animateTo(
            _scrollController.position.maxScrollExtent,
            duration: const Duration(milliseconds: 300),
            curve: Curves.easeOut,
          );
        });
      }
    } catch (e) {
      print('Error picking/analyzing file: $e');
      setState(() {
        _isUploadingFile = false;
      });

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Error uploading file: ${e.toString()}'),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  Future<String> _analyzeFileWithGemini(PlatformFile file) async {
    try {
      if (file.bytes == null) {
        throw Exception('File data not available');
      }

      final analysisResponse = await ApiService.analyzeFile(
        fileBytes: file.bytes!,
        filename: file.name,
        contentType: _getContentType(file.name),
      );

      if (analysisResponse['status'] == 'success') {
        return analysisResponse['analysis'] ?? 'File analyzed successfully';
      } else {
        throw Exception(
            'Analysis failed: ${analysisResponse['error'] ?? 'Unknown error'}');
      }
    } catch (e) {
      print('Error analyzing file with Gemini: $e');
      return 'Error analyzing file: ${e.toString()}';
    }
  }

  String _getContentType(String fileName) {
    final extension = fileName.toLowerCase().split('.').last;
    switch (extension) {
      case 'pdf':
        return 'application/pdf';
      case 'doc':
        return 'application/msword';
      case 'docx':
        return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
      case 'txt':
        return 'text/plain';
      case 'jpg':
      case 'jpeg':
        return 'image/jpeg';
      case 'png':
        return 'image/png';
      default:
        return 'application/octet-stream';
    }
  }

  Future<void> _sendMessage() async {
    final text = _controller.text.trim();
    print('Attempting to send message: "$text"');
    if (text.isEmpty) return;

    setState(() {
      _messages.add({'sender': 'user', 'text': text});
      _sending = true;
      _isAnalyzing = true;
      _analysisComplete = false;
      _controller.clear();
    });

    // Start red dot pulsing animation
    _redDotController.repeat(reverse: true);

    // Scroll to bottom
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _scrollController.animateTo(
        _scrollController.position.maxScrollExtent,
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeOut,
      );
    });

    try {
      print('Calling API service...');

      // Include context summary in the query if available
      String enhancedQuery = text;
      if (_contextSummary.isNotEmpty) {
        enhancedQuery = 'Context: $_contextSummary\n\nUser Query: $text';
      }

      // Include file analysis context if there are uploaded files
      if (_fileAnalysisResults.isNotEmpty) {
        String fileContext = '\n\nUploaded Files Analysis:\n';
        _fileAnalysisResults.forEach((filename, analysis) {
          fileContext += '• $filename: $analysis\n';
        });
        enhancedQuery += fileContext;
      }

      final response = await ApiService.sendQuery(queryText: enhancedQuery);
      print('API response received: $response');

      setState(() {
        final responseText = response['response_text'] ??
            'Sorry, I could not generate a response.';
        _messages.add({
          'sender': 'bot',
          'text': responseText,
          'request_id': response['request_id'],
        });
        _sending = false;
        _isAnalyzing = false;
        _analysisComplete = true;

        // Show treatment update button for substantial medical responses
        if (responseText.length > 100 &&
            (responseText.toLowerCase().contains('treatment') ||
                responseText.toLowerCase().contains('medication') ||
                responseText.toLowerCase().contains('therapy') ||
                responseText.toLowerCase().contains('recommend'))) {
          _showTreatmentUpdateButton = true;
          _latestResponseForTreatment = responseText;
          _latestRequestId = response['request_id'];
        }
      });

      // Stop pulsing and show completion state
      _redDotController.stop();
      _redDotController.reset();

      // Hide red dot after 3 seconds
      Future.delayed(const Duration(seconds: 3), () {
        if (mounted) {
          setState(() {
            _analysisComplete = false;
          });
        }
      });

      // Scroll to bottom after response
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      });
    } catch (e) {
      print('Error in _sendMessage: $e');
      setState(() {
        _messages.add({
          'sender': 'bot',
          'text': 'Sorry, I encountered an error: ${e.toString()}',
        });
        _sending = false;
        _isAnalyzing = false;
        _analysisComplete = false;
      });

      // Stop pulsing animation on error
      _redDotController.stop();
      _redDotController.reset();
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final size = MediaQuery.of(context).size;
    final isDark = theme.brightness == Brightness.dark;

    return Scaffold(
      backgroundColor: const Color(0xFFF8FAFC),
      appBar: AppBar(
        elevation: 0,
        backgroundColor: Colors.white,
        foregroundColor: const Color(0xFF1E293B),
        title: Row(
          children: [
            Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                  colors: [Color(0xFF3B82F6), Color(0xFF1D4ED8)],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
                borderRadius: BorderRadius.circular(12),
              ),
              child: const Icon(
                Icons.smart_toy,
                color: Colors.white,
                size: 20,
              ),
            ),
            SizedBox(width: 12),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Airavat AI',
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w600,
                    color: Color(0xFF1E293B),
                  ),
                ),
                Text(
                  'Medical Assistant',
                  style: TextStyle(
                    fontSize: 12,
                    color: Color(0xFF64748B),
                    fontWeight: FontWeight.w400,
                  ),
                ),
              ],
            ),
          ],
        ),
        actions: [
          IconButton(
            icon: Container(
              padding: EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: Color(0xFFF1F5F9),
                borderRadius: BorderRadius.circular(10),
              ),
              child: Icon(
                Icons.home_outlined,
                color: Color(0xFF64748B),
                size: 20,
              ),
            ),
            onPressed: () => context.go('/dashboard'),
            tooltip: 'Back to Dashboard',
          ),
          SizedBox(width: 8),
        ],
      ),
      body: FadeTransition(
        opacity: _fadeAnimation,
        child: SlideTransition(
          position: _slideAnimation,
          child: Column(
            children: [
              // Status bar
              Container(
                padding: EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                decoration: BoxDecoration(
                  color: Colors.white,
                  border: Border(
                    bottom: BorderSide(
                      color: Color(0xFFE2E8F0),
                      width: 1,
                    ),
                  ),
                ),
                child: Row(
                  children: [
                    Container(
                      width: 8,
                      height: 8,
                      decoration: BoxDecoration(
                        color: Color(0xFF10B981),
                        shape: BoxShape.circle,
                      ),
                    ),
                    SizedBox(width: 8),
                    Text(
                      'AI Assistant Online',
                      style: TextStyle(
                        fontSize: 14,
                        color: Color(0xFF64748B),
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                    Spacer(),
                    // Analysis status indicator
                    if (_isAnalyzing || _analysisComplete)
                      Container(
                        margin: EdgeInsets.only(right: 12),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            AnimatedBuilder(
                              animation: _redDotPulseAnimation,
                              builder: (context, child) {
                                return Container(
                                  width: 8,
                                  height: 8,
                                  decoration: BoxDecoration(
                                    color: _isAnalyzing
                                        ? Color(0xFFEF4444).withOpacity(
                                            _redDotPulseAnimation.value)
                                        : Color(
                                            0xFFEF4444), // Solid red when analysis complete
                                    shape: BoxShape.circle,
                                    boxShadow: _analysisComplete
                                        ? [
                                            BoxShadow(
                                              color: Color(0xFFEF4444)
                                                  .withOpacity(0.3),
                                              blurRadius: 4,
                                              spreadRadius: 2,
                                            ),
                                          ]
                                        : null,
                                  ),
                                );
                              },
                            ),
                            SizedBox(width: 6),
                            Text(
                              _isAnalyzing
                                  ? 'Analyzing...'
                                  : 'Analysis Complete',
                              style: TextStyle(
                                fontSize: 12,
                                color: Color(0xFFEF4444),
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ],
                        ),
                      ),
                    // File upload indicator
                    if (_uploadedFiles.isNotEmpty)
                      Container(
                        margin: EdgeInsets.only(right: 12),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(
                              Icons.attach_file,
                              size: 14,
                              color: Color(0xFF3B82F6),
                            ),
                            SizedBox(width: 4),
                            Text(
                              '${_uploadedFiles.length} file${_uploadedFiles.length > 1 ? 's' : ''}',
                              style: TextStyle(
                                fontSize: 12,
                                color: Color(0xFF3B82F6),
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ],
                        ),
                      ),
                    if (_currentUserId != null)
                      Container(
                        padding:
                            EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                        decoration: BoxDecoration(
                          color: Color(0xFFF1F5F9),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Text(
                          'ID: ${_currentUserId!.substring(0, 8)}...',
                          style: TextStyle(
                            fontSize: 12,
                            color: Color(0xFF64748B),
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ),
                  ],
                ),
              ),

              // Context History Widget
              if (_currentUserId != null && _showContextHistory)
                ContextHistoryWidget(
                  patientId: _currentUserId!,
                  onContextLoaded: _onContextLoaded,
                ),

              // Messages
              Expanded(
                child: Container(
                  color: Color(0xFFF8FAFC),
                  child: ListView.builder(
                    controller: _scrollController,
                    padding: EdgeInsets.all(20),
                    itemCount:
                        _messages.length + (_showTreatmentUpdateButton ? 1 : 0),
                    itemBuilder: (context, i) {
                      if (i == _messages.length && _showTreatmentUpdateButton) {
                        return _buildTreatmentUpdatePrompt();
                      }
                      final msg = _messages[i];
                      final isUser = msg['sender'] == 'user';
                      return _buildMessageBubble(msg, isUser, theme);
                    },
                  ),
                ),
              ),

              // Input area
              Container(
                padding: EdgeInsets.all(20),
                decoration: BoxDecoration(
                  color: Colors.white,
                  border: Border(
                    top: BorderSide(
                      color: Color(0xFFE2E8F0),
                      width: 1,
                    ),
                  ),
                ),
                child: SafeArea(
                  child: Row(
                    children: [
                      Expanded(
                        child: Container(
                          decoration: BoxDecoration(
                            color: Color(0xFFF8FAFC),
                            borderRadius: BorderRadius.circular(25),
                            border: Border.all(
                              color: _textFieldFocusNode.hasFocus
                                  ? Color(0xFF3B82F6)
                                  : Color(0xFFE2E8F0),
                              width: _textFieldFocusNode.hasFocus ? 2 : 1,
                            ),
                          ),
                          child: TextField(
                            controller: _controller,
                            focusNode: _textFieldFocusNode,
                            enabled: !_sending && _contextReady,
                            keyboardType: TextInputType.text,
                            textInputAction: TextInputAction.send,
                            maxLines: 1,
                            decoration: InputDecoration(
                              hintText: 'Ask me anything about your health...',
                              hintStyle: TextStyle(
                                color: Color(0xFF94A3B8),
                                fontSize: 16,
                                fontWeight: FontWeight.w400,
                              ),
                              border: InputBorder.none,
                              contentPadding: EdgeInsets.symmetric(
                                  horizontal: 20, vertical: 16),
                              suffixIcon: _sending
                                  ? Padding(
                                      padding: EdgeInsets.all(12.0),
                                      child: SizedBox(
                                        width: 20,
                                        height: 20,
                                        child: CircularProgressIndicator(
                                            strokeWidth: 2,
                                            color: Color(0xFF3B82F6)),
                                      ),
                                    )
                                  : null,
                            ),
                            onSubmitted: (_sending || !_contextReady)
                                ? null
                                : (_) => _sendMessage(),
                            onChanged: (value) {
                              setState(() {});
                            },
                            style: TextStyle(
                              fontSize: 16,
                              color: Color(0xFF1E293B),
                              fontWeight: FontWeight.w400,
                            ),
                          ),
                        ),
                      ),
                      SizedBox(width: 12),
                      // File upload button
                      Container(
                        decoration: BoxDecoration(
                          color: _isUploadingFile
                              ? Color(0xFFCBD5E1)
                              : Color(0xFFF1F5F9),
                          borderRadius: BorderRadius.circular(25),
                          border: Border.all(
                            color: Color(0xFFE2E8F0),
                            width: 1,
                          ),
                        ),
                        child: Material(
                          color: Colors.transparent,
                          child: InkWell(
                            borderRadius: BorderRadius.circular(25),
                            onTap:
                                _isUploadingFile ? null : _pickAndAnalyzeFile,
                            child: Container(
                              padding: EdgeInsets.all(16),
                              child: _isUploadingFile
                                  ? SizedBox(
                                      width: 20,
                                      height: 20,
                                      child: CircularProgressIndicator(
                                          strokeWidth: 2,
                                          color: Color(0xFF64748B)),
                                    )
                                  : Icon(
                                      Icons.attach_file_outlined,
                                      color: Color(0xFF64748B),
                                      size: 20,
                                    ),
                            ),
                          ),
                        ),
                      ),
                      SizedBox(width: 12),
                      Container(
                        decoration: BoxDecoration(
                          gradient: LinearGradient(
                            colors: _sending
                                ? [Color(0xFFCBD5E1), Color(0xFF94A3B8)]
                                : [Color(0xFF3B82F6), Color(0xFF1D4ED8)],
                            begin: Alignment.topLeft,
                            end: Alignment.bottomRight,
                          ),
                          borderRadius: BorderRadius.circular(25),
                          boxShadow: _sending
                              ? null
                              : [
                                  BoxShadow(
                                    color: Color(0xFF3B82F6).withOpacity(0.3),
                                    blurRadius: 8,
                                    offset: Offset(0, 4),
                                  ),
                                ],
                        ),
                        child: Material(
                          color: Colors.transparent,
                          child: InkWell(
                            borderRadius: BorderRadius.circular(25),
                            onTap: (_sending || !_contextReady)
                                ? null
                                : _sendMessage,
                            child: Container(
                              padding: EdgeInsets.all(16),
                              child: _sending
                                  ? SizedBox(
                                      width: 20,
                                      height: 20,
                                      child: CircularProgressIndicator(
                                          strokeWidth: 2, color: Colors.white),
                                    )
                                  : Icon(
                                      Icons.send_rounded,
                                      color: Colors.white,
                                      size: 20,
                                    ),
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildMessageBubble(
      Map<String, String> msg, bool isUser, ThemeData theme) {
    return Container(
      margin: EdgeInsets.only(bottom: 16),
      child: Row(
        mainAxisAlignment:
            isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (!isUser) ...[
            Stack(
              children: [
                Container(
                  width: 32,
                  height: 32,
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      colors: [Color(0xFF3B82F6), Color(0xFF1D4ED8)],
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                    ),
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Icon(
                    Icons.smart_toy,
                    color: Colors.white,
                    size: 16,
                  ),
                ),
                // Red dot indicator for analysis results
                if (msg['request_id'] != null)
                  Positioned(
                    top: 0,
                    right: 0,
                    child: Container(
                      width: 8,
                      height: 8,
                      decoration: BoxDecoration(
                        color: Color(0xFFEF4444),
                        shape: BoxShape.circle,
                        border: Border.all(
                          color: Colors.white,
                          width: 1,
                        ),
                        boxShadow: [
                          BoxShadow(
                            color: Color(0xFFEF4444).withOpacity(0.3),
                            blurRadius: 3,
                            spreadRadius: 1,
                          ),
                        ],
                      ),
                    ),
                  ),
              ],
            ),
            SizedBox(width: 8),
          ],
          Flexible(
            child: Container(
              constraints: BoxConstraints(
                maxWidth: MediaQuery.of(context).size.width * 0.75,
              ),
              padding: EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              decoration: BoxDecoration(
                color: isUser ? Color(0xFF3B82F6) : Colors.white,
                borderRadius: BorderRadius.circular(20),
                boxShadow: isUser
                    ? [
                        BoxShadow(
                          color: Color(0xFF3B82F6).withOpacity(0.2),
                          blurRadius: 8,
                          offset: Offset(0, 2),
                        ),
                      ]
                    : [
                        BoxShadow(
                          color: Colors.black.withOpacity(0.05),
                          blurRadius: 8,
                          offset: Offset(0, 2),
                        ),
                      ],
                border: isUser
                    ? null
                    : Border.all(
                        color: Color(0xFFE2E8F0),
                        width: 1,
                      ),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Analysis indicator for bot messages
                  if (!isUser && msg['request_id'] != null)
                    Container(
                      margin: EdgeInsets.only(bottom: 8),
                      padding: EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                      decoration: BoxDecoration(
                        color: Color(0xFFEF4444).withOpacity(0.1),
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(
                          color: Color(0xFFEF4444).withOpacity(0.3),
                          width: 1,
                        ),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Container(
                            width: 6,
                            height: 6,
                            decoration: BoxDecoration(
                              color: Color(0xFFEF4444),
                              shape: BoxShape.circle,
                            ),
                          ),
                          SizedBox(width: 6),
                          Text(
                            msg['file_related'] == 'true'
                                ? 'File Analysis Result'
                                : 'Gemini Analysis Result',
                            style: TextStyle(
                              fontSize: 11,
                              color: Color(0xFFEF4444),
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ],
                      ),
                    ),
                  // File upload indicator for user messages
                  if (isUser && msg['type'] == 'file_upload')
                    Container(
                      margin: EdgeInsets.only(bottom: 8),
                      padding: EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                      decoration: BoxDecoration(
                        color: Color(0xFF3B82F6).withOpacity(0.1),
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(
                          color: Color(0xFF3B82F6).withOpacity(0.3),
                          width: 1,
                        ),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(
                            Icons.attach_file,
                            size: 12,
                            color: Color(0xFF3B82F6),
                          ),
                          SizedBox(width: 4),
                          Text(
                            'File Upload',
                            style: TextStyle(
                              fontSize: 11,
                              color: Color(0xFF3B82F6),
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ],
                      ),
                    ),
                  Text(
                    msg['text'] ?? '',
                    style: TextStyle(
                      color: isUser ? Colors.white : Color(0xFF1E293B),
                      fontSize: 15,
                      fontWeight: FontWeight.w400,
                      height: 1.4,
                    ),
                  ),
                ],
              ),
            ),
          ),
          if (isUser) ...[
            SizedBox(width: 8),
            Container(
              width: 32,
              height: 32,
              decoration: BoxDecoration(
                color: Color(0xFFF1F5F9),
                borderRadius: BorderRadius.circular(16),
              ),
              child: Icon(
                Icons.person,
                color: Color(0xFF64748B),
                size: 16,
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildTreatmentUpdatePrompt() {
    final theme = Theme.of(context);

    return Container(
      margin: const EdgeInsets.only(bottom: 16, top: 8),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Container(
            constraints: BoxConstraints(
              maxWidth: MediaQuery.of(context).size.width * 0.9,
            ),
            child: Card(
              elevation: 8,
              shadowColor: theme.primaryColor.withOpacity(0.3),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(16),
              ),
              child: Container(
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    colors: [
                      theme.primaryColor,
                      theme.primaryColor.withOpacity(0.8),
                    ],
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                  ),
                  borderRadius: BorderRadius.circular(16),
                ),
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.all(8),
                          decoration: BoxDecoration(
                            color: Colors.white.withOpacity(0.2),
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: const Icon(
                            Icons.medical_services_outlined,
                            color: Colors.white,
                            size: 24,
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                'Lifelong Medical Assistant',
                                style: theme.textTheme.titleMedium?.copyWith(
                                  color: Colors.white,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                              const SizedBox(height: 4),
                              Text(
                                'Save Treatment Plan',
                                style: theme.textTheme.bodySmall?.copyWith(
                                  color: Colors.white.withOpacity(0.9),
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: Colors.white.withOpacity(0.1),
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(
                          color: Colors.white.withOpacity(0.2),
                          width: 1,
                        ),
                      ),
                      child: Text(
                        'Would you like to save this medical guidance as your latest treatment plan? This will help me provide better personalized care in future consultations.',
                        style: theme.textTheme.bodyMedium?.copyWith(
                          color: Colors.white,
                          height: 1.5,
                        ),
                      ),
                    ),
                    const SizedBox(height: 20),
                    Row(
                      children: [
                        Expanded(
                          child: OutlinedButton.icon(
                            onPressed: () {
                              setState(() {
                                _showTreatmentUpdateButton = false;
                                _latestResponseForTreatment = null;
                                _latestRequestId = null;
                              });
                            },
                            icon: const Icon(Icons.close, size: 16),
                            label: const Text('Not Now'),
                            style: OutlinedButton.styleFrom(
                              foregroundColor: Colors.white,
                              side: const BorderSide(
                                  color: Colors.white, width: 1.5),
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(8),
                              ),
                              padding: const EdgeInsets.symmetric(
                                  vertical: 12, horizontal: 16),
                            ),
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          flex: 2,
                          child: ElevatedButton.icon(
                            onPressed: _isAnalyzing
                                ? null
                                : _updateTreatmentInFirebase,
                            icon: _isAnalyzing
                                ? const SizedBox(
                                    width: 16,
                                    height: 16,
                                    child: CircularProgressIndicator(
                                      strokeWidth: 2,
                                      valueColor: AlwaysStoppedAnimation<Color>(
                                          Colors.grey),
                                    ),
                                  )
                                : const Icon(Icons.bookmark_add_outlined,
                                    size: 18),
                            label: Text(
                                _isAnalyzing ? 'Saving...' : 'Save to Profile'),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: Colors.white,
                              foregroundColor: theme.primaryColor,
                              disabledBackgroundColor:
                                  Colors.white.withOpacity(0.7),
                              disabledForegroundColor: Colors.grey,
                              elevation: 0,
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(8),
                              ),
                              padding: const EdgeInsets.symmetric(
                                  vertical: 12, horizontal: 16),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
