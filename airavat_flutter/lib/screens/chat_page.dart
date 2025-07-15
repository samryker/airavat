import 'package:flutter/material.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:go_router/go_router.dart';
import '../services/api_service.dart';

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
  String? _currentUserId;
  late AnimationController _fadeController;
  late AnimationController _slideController;
  late Animation<double> _fadeAnimation;
  late Animation<Offset> _slideAnimation;
  Map<String, dynamic>? _patientContext; // Added for patient context

  @override
  void initState() {
    super.initState();
    _loadUserData();

    // Initialize animations
    _fadeController = AnimationController(
      duration: Duration(milliseconds: 800),
      vsync: this,
    );
    _slideController = AnimationController(
      duration: Duration(milliseconds: 600),
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
      begin: Offset(0, 0.3),
      end: Offset.zero,
    ).animate(CurvedAnimation(
      parent: _slideController,
      curve: Curves.easeOutCubic,
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
        final contextResponse = await ApiService.getPatientContextFromBackend();
        if (contextResponse['status'] == 'success') {
          final context = contextResponse['context'];
          print('Loaded patient context: ${context.keys}');

          // Store context for use in conversations
          _patientContext = context;
        }
      } catch (e) {
        print('Error loading patient context: $e');
      }
    }
  }

  Future<void> _sendMessage() async {
    final text = _controller.text.trim();
    print('Attempting to send message: "$text"');
    if (text.isEmpty) return;

    setState(() {
      _messages.add({'sender': 'user', 'text': text});
      _sending = true;
      _controller.clear();
    });

    // Scroll to bottom
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _scrollController.animateTo(
        _scrollController.position.maxScrollExtent,
        duration: Duration(milliseconds: 300),
        curve: Curves.easeOut,
      );
    });

    try {
      print('Calling API service...');
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

      // Scroll to bottom after response
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: Duration(milliseconds: 300),
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
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final size = MediaQuery.of(context).size;
    final isDark = theme.brightness == Brightness.dark;

    return Scaffold(
      backgroundColor: Color(0xFFF8FAFC),
      appBar: AppBar(
        elevation: 0,
        backgroundColor: Colors.white,
        foregroundColor: Color(0xFF1E293B),
        title: Row(
          children: [
            Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: [Color(0xFF3B82F6), Color(0xFF1D4ED8)],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Icon(
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

              // Messages
              Expanded(
                child: Container(
                  color: Color(0xFFF8FAFC),
                  child: ListView.builder(
                    controller: _scrollController,
                    padding: EdgeInsets.all(20),
                    itemCount: _messages.length,
                    itemBuilder: (context, i) {
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
                            enabled: !_sending,
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
                            onSubmitted:
                                _sending ? null : (_) => _sendMessage(),
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
                            onTap: _sending ? null : _sendMessage,
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
              child: Text(
                msg['text'] ?? '',
                style: TextStyle(
                  color: isUser ? Colors.white : Color(0xFF1E293B),
                  fontSize: 15,
                  fontWeight: FontWeight.w400,
                  height: 1.4,
                ),
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
}
