// lib/screens/dashboard_screen.dart
import 'package:flutter/material.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:file_picker/file_picker.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:go_router/go_router.dart';
import 'package:provider/provider.dart';
import '../services/api_service.dart';
import '../services/twin_service.dart';
import '../widgets/webgl_twin_widget.dart';
import '../providers/theme_provider.dart';
import '../config/theme_config.dart';
import '../widgets/smpl_controls.dart';

class DashboardScreen extends StatefulWidget {
  @override
  _DashboardScreenState createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen>
    with WidgetsBindingObserver {
  List<PlatformFile> _files = [];
  List<Map<String, String>> _messages = [];
  final TextEditingController _controller = TextEditingController();
  final FocusNode _textFieldFocusNode = FocusNode();
  bool _sending = false;
  String? _currentUserId;
  Map<String, dynamic>? _userBiomarkers;
  String? _userModelUrl;
  bool _isChatOpen = false;
  String _selectedOrgan = 'Heart';
  List<Map<String, dynamic>> _treatmentHistory = [];
  bool _isLoadingTreatments = false;
  List<Map<String, dynamic>> _notifications = [];
  bool _isLoadingNotifications = false;
  // SMPL parameters controlled by Flutter UI
  String _smplGender = 'neutral';
  double _smplHeight = 170;
  double _smplWeight = 70;
  double _smplBeta1 = 0.4;

  final List<String> _organSystems = [
    'Heart',
    'Brain',
    'Kidney',
    'Eyes',
    'Liver',
    'Lungs',
    'Stomach',
    'Bones',
    'Skin',
    'Blood',
    'Immune',
    'Endocrine'
  ];

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _loadUserData();
    _loadNotifications();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _textFieldFocusNode.dispose();
    _controller.dispose();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    super.didChangeAppLifecycleState(state);
    if (state == AppLifecycleState.resumed) {
      // Refresh data when app comes back to foreground
      print('DashboardScreen: App resumed, refreshing data');
      _refreshTreatmentHistory();
      _loadNotifications();
    }
  }

  Future<void> _loadUserData() async {
    final user = FirebaseAuth.instance.currentUser;
    if (user != null) {
      setState(() {
        _currentUserId = user.uid;
      });

      // Load treatment history
      await _loadTreatmentHistory();

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

  Future<void> _loadTreatmentHistory() async {
    if (_currentUserId == null) {
      print(
          'DashboardScreen: No current user ID, skipping treatment history load');
      return;
    }

    print(
        'DashboardScreen: Loading treatment history for user: $_currentUserId');

    setState(() {
      _isLoadingTreatments = true;
    });

    try {
      // Get treatment plans directly from Firestore patients collection
      final doc = await FirebaseFirestore.instance
          .collection('patients')
          .doc(_currentUserId)
          .get();

      print('DashboardScreen: Patient document exists: ${doc.exists}');

      if (doc.exists) {
        final data = doc.data()!;
        List<Map<String, dynamic>> treatments = [];

        // Get latest treatment from separate collection (most recent)
        final latestTreatmentDoc = await FirebaseFirestore.instance
            .collection('latest_treatment')
            .doc(_currentUserId)
            .get();

        print(
            'DashboardScreen: Latest treatment document exists: ${latestTreatmentDoc.exists}');

        if (latestTreatmentDoc.exists) {
          final latestData = latestTreatmentDoc.data()!;
          final treatmentData =
              latestData['treatment_data'] as Map<String, dynamic>;
          treatments.add({
            'text': treatmentData['treatment_text'] ?? 'Latest Treatment',
            'timestamp':
                treatmentData['timestamp'] ?? DateTime.now().toIso8601String(),
            'type': 'latest_treatment',
            'request_id': treatmentData['request_id'] ?? '',
            'source': 'ai_assistant',
            'plan_type': 'latest',
            'is_latest': true,
          });
          print(
              'DashboardScreen: Added latest treatment: ${treatmentData['treatment_text']}');
        }

        // Get comprehensive treatment plans from patient document
        final treatmentPlans = data['treatmentPlans'] as List? ?? [];
        print(
            'DashboardScreen: Found ${treatmentPlans.length} treatment plans in patient document');

        if (treatmentPlans.isNotEmpty) {
          print('DashboardScreen: Treatment plans data: $treatmentPlans');
        }

        final historicalTreatments = treatmentPlans
            .map((plan) => {
                  'text': plan['treatment_text'] ??
                      plan['text'] ??
                      plan['treatmentName'] ??
                      'Treatment plan',
                  'timestamp':
                      plan['timestamp'] ?? DateTime.now().toIso8601String(),
                  'type': plan['type'] ?? 'treatment',
                  'request_id': plan['request_id'] ?? '',
                  'source': plan['source'] ?? 'ai_assistant',
                  'plan_type': plan['plan_type'] ?? 'general',
                  'priority': plan['priority'] ?? 'medium',
                  'status': plan['status'] ?? 'active',
                  'biomarkers': plan['biomarkers'] ?? {},
                  'medications': plan['medications'] ?? [],
                  'recommendations': plan['recommendations'] ?? [],
                  'is_latest': false,
                })
            .toList();

        print(
            'DashboardScreen: Processed ${historicalTreatments.length} historical treatments');

        // Sort treatments by timestamp (newest first)
        historicalTreatments.sort((a, b) {
          final aTime = DateTime.tryParse(a['timestamp']) ?? DateTime.now();
          final bTime = DateTime.tryParse(b['timestamp']) ?? DateTime.now();
          return bTime.compareTo(aTime);
        });

        treatments.addAll(historicalTreatments.cast<Map<String, dynamic>>());

        // Sort by timestamp (newest first)
        treatments.sort((a, b) {
          final timeA = DateTime.tryParse(a['timestamp']) ?? DateTime.now();
          final timeB = DateTime.tryParse(b['timestamp']) ?? DateTime.now();
          return timeB.compareTo(timeA);
        });

        print(
            'DashboardScreen: Total treatments to display: ${treatments.length}');

        setState(() {
          _treatmentHistory = treatments;
        });
      } else {
        print('DashboardScreen: Patient document does not exist');
        setState(() {
          _treatmentHistory = [];
        });
      }
    } catch (e) {
      print('DashboardScreen: Error loading treatment history: $e');
      // Show a snackbar to user
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Error loading treatment history: $e'),
            backgroundColor: Colors.red,
          ),
        );
      }
    } finally {
      setState(() {
        _isLoadingTreatments = false;
      });
    }
  }

  Future<void> _loadNotifications() async {
    if (_currentUserId == null) return;

    setState(() {
      _isLoadingNotifications = true;
    });

    try {
      final notifications =
          await ApiService.getUserNotifications(_currentUserId!);
      setState(() {
        _notifications = notifications;
      });
    } catch (e) {
      print('Error loading notifications: $e');
      setState(() {
        _notifications = [];
      });
    } finally {
      setState(() {
        _isLoadingNotifications = false;
      });
    }
  }

  Future<void> _logout() async {
    await FirebaseAuth.instance.signOut();
    if (!mounted) return;
    context.go('/login');
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    final Size _screenSize = MediaQuery.of(context).size;
    final bool _isMobile = _screenSize.width < 768;

    if (_isMobile) {
      return Scaffold(
        backgroundColor: theme.scaffoldBackgroundColor,
        appBar: _buildMobileAppBar(context, isDark),
        drawer: _buildMobileDrawer(context, isDark),
        body: SafeArea(
          child: SingleChildScrollView(
            child: Padding(
              padding: const EdgeInsets.all(16.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _buildOrganOverview(context, isDark),
                  const SizedBox(height: 24),
                  _buildTreatmentHistoryHeader(
                      Theme.of(context).textTheme, theme),
                  const SizedBox(height: 12),
                  _buildMobileTreatmentHistory(context, isDark),
                  const SizedBox(height: 24),
                  _buildSectionTitle(
                      'Medical Metrics', Theme.of(context).textTheme, theme),
                  const SizedBox(height: 12),
                  _buildMobileMetricsList(context, isDark),
                  const SizedBox(height: 24),
                  _buildSectionTitle(
                      'Tasks & Reminders', Theme.of(context).textTheme, theme),
                  const SizedBox(height: 12),
                  _buildMobileNotifications(context, isDark),
                ],
              ),
            ),
          ),
        ),
      );
    } else {
      return Scaffold(
        backgroundColor: theme.scaffoldBackgroundColor,
        body: Row(
          children: [
            // Left Sidebar
            _buildSidebar(context, isDark),

            // Main Content
            Expanded(
              child: Column(
                children: [
                  // Top Header
                  _buildTopHeader(context, isDark),

                  // Main Dashboard Content
                  Expanded(
                    child: Padding(
                      padding: const EdgeInsets.all(24.0),
                      child: Row(
                        children: [
                          // Left Column - Organ Overview
                          Expanded(
                            flex: 2,
                            child: _buildOrganOverview(context, isDark),
                          ),

                          const SizedBox(width: 24),

                          // Right Column - Metrics & Appointments
                          Expanded(
                            flex: 1,
                            child: _buildRightColumn(context, isDark),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      );
    }
  }

  Widget _buildSidebar(BuildContext context, bool isDark) {
    final theme = Theme.of(context);
    final textTheme = theme.textTheme;
    final screenSize = MediaQuery.of(context).size;
    final isMobile = screenSize.width < 768;

    return Container(
      width: isMobile ? screenSize.width * 0.8 : 300,
      height: screenSize.height,
      color: theme.colorScheme.surface,
      child: Column(
        children: [
          Container(
            padding: EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: theme.primaryColor,
              borderRadius: BorderRadius.only(
                bottomLeft: Radius.circular(20),
                bottomRight: Radius.circular(20),
              ),
            ),
            child: Row(
              children: [
                Icon(
                  Icons.medical_services_outlined,
                  color: Colors.white,
                  size: 30,
                ),
                SizedBox(width: 10),
                Text(
                  'Airavat',
                  style: textTheme.titleLarge?.copyWith(
                    color: Colors.white,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
          ),
          SizedBox(height: 20),
          ListTile(
            leading: Icon(Icons.home, color: theme.primaryColor),
            title: Text('Dashboard', style: textTheme.bodyMedium),
            onTap: () => context.go('/dashboard'),
          ),
          ListTile(
            leading: Icon(Icons.chat_bubble_outline, color: theme.primaryColor),
            title: Text('Chat with AI', style: textTheme.bodyMedium),
            onTap: () => context.go('/chat'),
          ),
          ListTile(
            leading:
                Icon(Icons.account_circle_outlined, color: theme.primaryColor),
            title: Text('Account', style: textTheme.bodyMedium),
            onTap: () => context.go('/account'),
          ),
          ListTile(
            leading: Icon(Icons.logout_outlined, color: theme.primaryColor),
            title: Text('Log Out', style: textTheme.bodyMedium),
            onTap: _logout,
          ),
        ],
      ),
    );
  }

  Widget _buildTopHeader(BuildContext context, bool isDark) {
    final theme = Theme.of(context);
    final textTheme = theme.textTheme;
    final screenSize = MediaQuery.of(context).size;
    final isMobile = screenSize.width < 768;

    return Container(
      padding: EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: theme.colorScheme.surface,
        border: Border(
          bottom: BorderSide(color: theme.dividerColor),
        ),
      ),
      child: Row(
        children: [
          Icon(
            Icons.medical_services_outlined,
            color: theme.primaryColor,
            size: 30,
          ),
          SizedBox(width: 10),
          Text(
            'Airavat Digital Twin',
            style: textTheme.titleLarge?.copyWith(
              fontWeight: FontWeight.bold,
              color: theme.primaryColor,
            ),
          ),
          Spacer(),
          Consumer<ThemeProvider>(
            builder: (context, themeProvider, child) {
              return IconButton(
                icon: Icon(
                  themeProvider.isDarkMode ? Icons.light_mode : Icons.dark_mode,
                  color: theme.primaryColor,
                ),
                onPressed: () {
                  themeProvider.toggleTheme();
                },
                tooltip: themeProvider.isDarkMode ? 'Light Mode' : 'Dark Mode',
              );
            },
          ),
          if (_currentUserId != null)
            Container(
              padding: EdgeInsets.symmetric(horizontal: 8, vertical: 4),
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
    );
  }

  Widget _buildOrganOverview(BuildContext context, bool isDark) {
    final theme = Theme.of(context);
    final textTheme = theme.textTheme;
    final screenSize = MediaQuery.of(context).size;
    final isMobile = screenSize.width < 768;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildSectionTitle('Organ Overview', textTheme, theme),
        SizedBox(height: 16),
        Container(
          height: isMobile ? 420 : screenSize.height * 0.5,
          child: WebGLTwinWidget(
            userId: _currentUserId,
            userBiomarkers: _userBiomarkers,
            modelUrl: _userModelUrl,
            initialGender: _smplGender,
            initialHeightCm: _smplHeight,
            initialWeightKg: _smplWeight,
            initialBeta1: _smplBeta1,
            onOrganSelected: (organ) {
              setState(() {
                _selectedOrgan = organ;
              });
            },
          ),
        ),
        const SizedBox(height: 12),
        // SMPL Controls (Flutter)
        SmplControls(
          onChange: (
              {String? gender, double? height, double? weight, double? beta1}) {
            setState(() {
              if (gender != null) _smplGender = gender;
              if (height != null) _smplHeight = height;
              if (weight != null) _smplWeight = weight;
              if (beta1 != null) _smplBeta1 = beta1;
            });
          },
        ),
        SizedBox(height: 20),
        if (!isMobile) ...[
          _buildTreatmentHistoryHeader(textTheme, theme),
          SizedBox(height: 16),
          Expanded(child: _buildDesktopTreatmentHistoryList(context, isDark)),
        ],
      ],
    );
  }

  Widget _buildRightColumn(BuildContext context, bool isDark) {
    final theme = Theme.of(context);
    final textTheme = theme.textTheme;
    final screenSize = MediaQuery.of(context).size;
    final isMobile = screenSize.width < 768;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildSectionTitle('Medical Metrics', textTheme, theme),
        SizedBox(height: 16),
        if (!isMobile) Expanded(child: _buildMetricsListView(context, isDark)),
        SizedBox(height: 20),
        _buildSectionTitle('Tasks & Reminders', textTheme, theme),
        SizedBox(height: 16),
        if (!isMobile)
          Expanded(child: _buildNotificationsList(context, isDark)),
      ],
    );
  }

  Widget _buildSectionTitle(
      String title, TextTheme textTheme, ThemeData theme) {
    return Text(
      title,
      style: textTheme.titleLarge?.copyWith(
        fontWeight: FontWeight.bold,
        color: theme.colorScheme.onSurface,
      ),
    );
  }

  Widget _buildTreatmentHistoryHeader(TextTheme textTheme, ThemeData theme) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(
          'Treatment History',
          style: textTheme.titleLarge?.copyWith(
            fontWeight: FontWeight.bold,
            color: theme.colorScheme.onSurface,
          ),
        ),
        Row(
          children: [
            if (_treatmentHistory.isNotEmpty)
              Text(
                '${_treatmentHistory.length} treatments',
                style: textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurface.withOpacity(0.6),
                ),
              ),
            SizedBox(width: 8),
            IconButton(
              onPressed: _refreshTreatmentHistory,
              icon: Icon(
                Icons.refresh,
                color: theme.primaryColor,
              ),
              tooltip: 'Refresh Treatment History',
              iconSize: 20,
            ),
          ],
        ),
      ],
    );
  }

  Future<void> _refreshTreatmentHistory() async {
    print('DashboardScreen: Manual refresh triggered');
    await _loadTreatmentHistory();
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Treatment history refreshed'),
          duration: Duration(seconds: 2),
        ),
      );
    }
  }

  String _getTimeAgo(DateTime timestamp) {
    final now = DateTime.now();
    final difference = now.difference(timestamp);

    if (difference.inDays > 0) {
      return '${difference.inDays} day${difference.inDays > 1 ? 's' : ''} ago';
    } else if (difference.inHours > 0) {
      return '${difference.inHours} hour${difference.inHours > 1 ? 's' : ''} ago';
    } else if (difference.inMinutes > 0) {
      return '${difference.inMinutes} minute${difference.inMinutes > 1 ? 's' : ''} ago';
    } else {
      return 'Just now';
    }
  }

  Widget _getOrganIcon(String organ) {
    IconData iconData;
    Color iconColor;

    switch (organ.toLowerCase()) {
      case 'heart':
        iconData = Icons.favorite;
        iconColor = Colors.red;
        break;
      case 'brain':
        iconData = Icons.psychology;
        iconColor = Colors.purple;
        break;
      case 'kidney':
        iconData = Icons.water_drop;
        iconColor = Colors.blue;
        break;
      case 'eyes':
        iconData = Icons.visibility;
        iconColor = Colors.green;
        break;
      case 'liver':
        iconData = Icons.hexagon;
        iconColor = Colors.brown;
        break;
      case 'lungs':
        iconData = Icons.air;
        iconColor = Colors.cyan;
        break;
      case 'stomach':
        iconData = Icons.circle;
        iconColor = Colors.orange;
        break;
      case 'bones':
        iconData = Icons.healing;
        iconColor = Colors.grey.shade600;
        break;
      case 'skin':
        iconData = Icons.face;
        iconColor = Colors.pink;
        break;
      case 'blood':
        iconData = Icons.bloodtype;
        iconColor = Colors.redAccent;
        break;
      case 'immune':
        iconData = Icons.shield;
        iconColor = Colors.teal;
        break;
      case 'endocrine':
        iconData = Icons.scatter_plot;
        iconColor = Colors.deepPurple;
        break;
      default:
        iconData = Icons.medical_services;
        iconColor = Colors.grey;
    }

    return Container(
      padding: EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: iconColor.withOpacity(0.1),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: iconColor.withOpacity(0.3), width: 1),
      ),
      child: Icon(
        iconData,
        color: iconColor,
        size: 24,
      ),
    );
  }

  Map<String, dynamic> _getOrganDetails(String organ) {
    switch (organ.toLowerCase()) {
      case 'heart':
        return {
          'color': Colors.red,
          'description':
              'Access comprehensive cardiovascular analysis with AI-powered insights into heart health, rhythm patterns, and risk assessment.',
          'features': [
            'ECG pattern analysis',
            'Heart rate variability tracking',
            'Blood pressure optimization',
            'Cardiac risk assessment',
            'Cholesterol management insights'
          ]
        };
      case 'brain':
        return {
          'color': Colors.purple,
          'description':
              'Unlock advanced neurological insights with cognitive health monitoring and brain performance optimization.',
          'features': [
            'Cognitive performance tracking',
            'Memory assessment tools',
            'Stress level analysis',
            'Sleep pattern optimization',
            'Mental health indicators'
          ]
        };
      case 'kidney':
        return {
          'color': Colors.blue,
          'description':
              'Monitor renal function with comprehensive kidney health analysis and filtration efficiency tracking.',
          'features': [
            'Kidney function testing',
            'Filtration rate monitoring',
            'Electrolyte balance tracking',
            'Toxin level assessment',
            'Hydration optimization'
          ]
        };
      case 'eyes':
        return {
          'color': Colors.green,
          'description':
              'Comprehensive vision health analysis with retinal imaging and visual acuity optimization.',
          'features': [
            'Visual acuity testing',
            'Retinal health scanning',
            'Eye pressure monitoring',
            'Color vision assessment',
            'Digital eye strain analysis'
          ]
        };
      case 'liver':
        return {
          'color': Colors.brown,
          'description':
              'Advanced hepatic function analysis with detoxification monitoring and metabolic health insights.',
          'features': [
            'Liver enzyme tracking',
            'Detoxification efficiency',
            'Fat metabolism analysis',
            'Bile production monitoring',
            'Toxin clearance assessment'
          ]
        };
      case 'lungs':
        return {
          'color': Colors.cyan,
          'description':
              'Respiratory health optimization with lung capacity analysis and breathing pattern monitoring.',
          'features': [
            'Lung capacity testing',
            'Oxygen saturation tracking',
            'Breathing pattern analysis',
            'Air quality impact assessment',
            'Respiratory efficiency optimization'
          ]
        };
      case 'stomach':
        return {
          'color': Colors.orange,
          'description':
              'Digestive health monitoring with gastric function analysis and nutrient absorption tracking.',
          'features': [
            'Digestive enzyme analysis',
            'Gut microbiome tracking',
            'Nutrient absorption monitoring',
            'Acid level optimization',
            'Food sensitivity detection'
          ]
        };
      case 'bones':
        return {
          'color': Colors.grey.shade600,
          'description':
              'Comprehensive bone health analysis with density monitoring and fracture risk assessment.',
          'features': [
            'Bone density scanning',
            'Calcium absorption tracking',
            'Fracture risk assessment',
            'Joint health monitoring',
            'Mobility optimization'
          ]
        };
      case 'skin':
        return {
          'color': Colors.pink,
          'description':
              'Advanced dermatological analysis with skin health monitoring and aging assessment.',
          'features': [
            'Skin elasticity testing',
            'UV damage assessment',
            'Hydration level monitoring',
            'Age spot analysis',
            'Cancer risk screening'
          ]
        };
      case 'blood':
        return {
          'color': Colors.redAccent,
          'description':
              'Comprehensive hematological analysis with blood cell monitoring and circulation assessment.',
          'features': [
            'Complete blood count analysis',
            'Circulation efficiency tracking',
            'Clotting factor assessment',
            'Oxygen transport monitoring',
            'Infection marker detection'
          ]
        };
      case 'immune':
        return {
          'color': Colors.teal,
          'description':
              'Immune system optimization with defense mechanism analysis and infection resistance tracking.',
          'features': [
            'Immune cell count monitoring',
            'Antibody level tracking',
            'Inflammation marker analysis',
            'Infection resistance assessment',
            'Autoimmune risk evaluation'
          ]
        };
      case 'endocrine':
        return {
          'color': Colors.deepPurple,
          'description':
              'Hormonal balance optimization with endocrine system monitoring and metabolic regulation analysis.',
          'features': [
            'Hormone level tracking',
            'Thyroid function monitoring',
            'Insulin sensitivity analysis',
            'Growth factor assessment',
            'Metabolic rate optimization'
          ]
        };
      default:
        return {
          'color': Colors.grey,
          'description':
              'Access detailed medical analysis and insights with comprehensive health monitoring.',
          'features': [
            'Detailed organ analysis',
            'Real-time health monitoring',
            'Advanced biomarker tracking',
            'Personalized recommendations',
            'AI-powered insights'
          ]
        };
    }
  }

  void _showPremiumDialog(BuildContext context, String organ) {
    // Get organ-specific content
    Map<String, dynamic> organDetails = _getOrganDetails(organ);

    showDialog(
      context: context,
      builder: (BuildContext context) {
        return AlertDialog(
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
          ),
          title: Row(
            children: [
              _getOrganIcon(organ),
              SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '${organ.toUpperCase()} Analysis',
                      style: TextStyle(
                        color: organDetails['color'],
                        fontWeight: FontWeight.bold,
                        fontSize: 18,
                      ),
                    ),
                    Text(
                      'Premium Feature',
                      style: TextStyle(
                        color: Colors.amber.shade700,
                        fontSize: 14,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  organDetails['description'],
                  style: TextStyle(fontSize: 16, height: 1.4),
                ),
                SizedBox(height: 16),
                Container(
                  padding: EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: organDetails['color'].withOpacity(0.1),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(
                        color: organDetails['color'].withOpacity(0.3)),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Premium ${organ.toUpperCase()} Features:',
                        style: TextStyle(
                          fontWeight: FontWeight.w600,
                          color: organDetails['color'],
                          fontSize: 16,
                        ),
                      ),
                      SizedBox(height: 8),
                      ...organDetails['features']
                          .map<Widget>((feature) => Padding(
                                padding: EdgeInsets.symmetric(vertical: 2),
                                child: Row(
                                  children: [
                                    Icon(Icons.check_circle,
                                        size: 16, color: organDetails['color']),
                                    SizedBox(width: 8),
                                    Expanded(child: Text(feature)),
                                  ],
                                ),
                              ))
                          .toList(),
                    ],
                  ),
                ),
                SizedBox(height: 16),
                Container(
                  padding: EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: Colors.blue.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: Colors.blue.withOpacity(0.3)),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'AI-Powered Insights:',
                        style: TextStyle(
                          fontWeight: FontWeight.w600,
                          color: Colors.blue.shade700,
                        ),
                      ),
                      SizedBox(height: 8),
                      Text('• Real-time biomarker analysis'),
                      Text('• Predictive health modeling'),
                      Text('• Personalized treatment plans'),
                      Text('• Integration with genetic data'),
                    ],
                  ),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: Text('Maybe Later'),
            ),
            ElevatedButton.icon(
              onPressed: () {
                Navigator.of(context).pop();
                _contactAdmin();
              },
              icon: Icon(Icons.email),
              label: Text('Contact Admin'),
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.amber,
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(8),
                ),
              ),
            ),
          ],
        );
      },
    );
  }

  void _contactAdmin() {
    showDialog(
      context: context,
      builder: (BuildContext context) {
        return AlertDialog(
          title: Text('Contact Admin'),
          content: Text(
            'Please contact our admin team for Premium upgrade:\n\n'
            'Email: admin@airavat.ai\n'
            'Phone: +1 (555) 123-4567\n\n'
            'Or reach out through our support portal.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: Text('Close'),
            ),
          ],
        );
      },
    );
  }

  Widget _getNotificationIcon(String notificationType) {
    IconData iconData;
    Color iconColor;

    switch (notificationType.toLowerCase()) {
      case 'medication_reminder':
        iconData = Icons.medication;
        iconColor = Colors.green;
        break;
      case 'appointment_reminder':
        iconData = Icons.calendar_today;
        iconColor = Colors.blue;
        break;
      case 'health_check':
        iconData = Icons.health_and_safety;
        iconColor = Colors.red;
        break;
      case 'general_reminder':
      default:
        iconData = Icons.notifications;
        iconColor = Colors.orange;
        break;
    }

    return Container(
      padding: EdgeInsets.all(6),
      decoration: BoxDecoration(
        color: iconColor.withOpacity(0.1),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Icon(
        iconData,
        color: iconColor,
        size: 20,
      ),
    );
  }

  Color _getPriorityColor(String priority) {
    switch (priority.toLowerCase()) {
      case 'high':
      case 'urgent':
        return Colors.red;
      case 'medium':
        return Colors.orange;
      case 'low':
      default:
        return Colors.green;
    }
  }

  Color _getStatusColor(String status) {
    switch (status.toLowerCase()) {
      case 'sent':
      case 'completed':
        return Colors.green;
      case 'pending':
        return Colors.orange;
      case 'failed':
        return Colors.red;
      default:
        return Colors.grey;
    }
  }

  PreferredSizeWidget _buildMobileAppBar(BuildContext context, bool isDark) {
    final theme = Theme.of(context);
    final textTheme = theme.textTheme;
    return AppBar(
      backgroundColor: theme.primaryColor,
      elevation: 0,
      leading: Builder(
        builder: (context) => IconButton(
          icon: Icon(Icons.menu, color: Colors.white),
          onPressed: () => Scaffold.of(context).openDrawer(),
        ),
      ),
      title: Row(
        children: [
          Icon(Icons.medical_services_outlined, color: Colors.white, size: 26),
          SizedBox(width: 8),
          Text(
            'Airavat',
            style: textTheme.titleLarge?.copyWith(
              color: Colors.white,
              fontWeight: FontWeight.bold,
            ),
          ),
        ],
      ),
      actions: [
        Consumer<ThemeProvider>(
          builder: (context, themeProvider, child) {
            return IconButton(
              icon: Icon(
                themeProvider.isDarkMode ? Icons.light_mode : Icons.dark_mode,
                color: Colors.white,
              ),
              onPressed: () => themeProvider.toggleTheme(),
            );
          },
        ),
      ],
    );
  }

  Widget _buildMobileDrawer(BuildContext context, bool isDark) {
    final theme = Theme.of(context);
    final textTheme = theme.textTheme;
    return Drawer(
      backgroundColor: theme.colorScheme.surface,
      child: Column(
        children: [
          Container(
            padding: EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: theme.primaryColor,
              borderRadius: BorderRadius.only(
                bottomLeft: Radius.circular(16),
                bottomRight: Radius.circular(16),
              ),
            ),
            child: Row(
              children: [
                Icon(Icons.medical_services_outlined,
                    color: Colors.white, size: 28),
                SizedBox(width: 12),
                Text('Airavat',
                    style: textTheme.titleLarge?.copyWith(
                        color: Colors.white, fontWeight: FontWeight.bold)),
              ],
            ),
          ),
          SizedBox(height: 16),
          ListTile(
            leading: Icon(Icons.home, color: theme.primaryColor),
            title: Text('Dashboard', style: textTheme.bodyLarge),
            onTap: () {
              Navigator.of(context).pop();
              context.go('/dashboard');
            },
          ),
          ListTile(
            leading: Icon(Icons.chat_bubble_outline, color: theme.primaryColor),
            title: Text('Chat with AI', style: textTheme.bodyLarge),
            onTap: () {
              Navigator.of(context).pop();
              context.go('/chat');
            },
          ),
          ListTile(
            leading:
                Icon(Icons.account_circle_outlined, color: theme.primaryColor),
            title: Text('Account', style: textTheme.bodyLarge),
            onTap: () {
              Navigator.of(context).pop();
              context.go('/account');
            },
          ),
          Spacer(),
          ListTile(
            leading: Icon(Icons.logout_outlined, color: theme.primaryColor),
            title: Text('Log Out', style: textTheme.bodyLarge),
            onTap: () {
              Navigator.of(context).pop();
              _logout();
            },
          ),
        ],
      ),
    );
  }

  Widget _buildDesktopTreatmentHistoryList(BuildContext context, bool isDark) {
    final theme = Theme.of(context);
    final textTheme = theme.textTheme;
    if (_isLoadingTreatments) {
      return Center(
          child: CircularProgressIndicator(color: theme.primaryColor));
    }
    if (_treatmentHistory.isEmpty) {
      return Center(child: _buildEmptyState(context, isDark));
    }
    return ListView.builder(
      itemCount: _treatmentHistory.length,
      itemBuilder: (context, index) {
        final treatment = _treatmentHistory[index];
        final timestamp = DateTime.parse(treatment['timestamp']);
        final timeAgo = _getTimeAgo(timestamp);
        final isLatest = treatment['is_latest'] == true;
        return Padding(
          padding: const EdgeInsets.symmetric(vertical: 8.0),
          child: Card(
            elevation: isLatest ? 6 : 2,
            color: isLatest ? theme.primaryColor.withOpacity(0.05) : null,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
              side: isLatest
                  ? BorderSide(
                      color: theme.primaryColor.withOpacity(0.3), width: 2)
                  : BorderSide.none,
            ),
            child: Padding(
              padding: const EdgeInsets.all(12.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(isLatest ? Icons.star : Icons.medical_services,
                          size: 16,
                          color: isLatest ? Colors.amber : theme.primaryColor),
                      SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          isLatest ? 'Latest Treatment - $timeAgo' : timeAgo,
                          style: textTheme.bodySmall?.copyWith(
                            color: isLatest
                                ? Colors.amber.shade700
                                : theme.primaryColor,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                      if (isLatest)
                        Container(
                          padding:
                              EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                          decoration: BoxDecoration(
                              color: Colors.amber,
                              borderRadius: BorderRadius.circular(12)),
                          child: Text('LATEST',
                              style: TextStyle(
                                  color: Colors.white,
                                  fontSize: 10,
                                  fontWeight: FontWeight.bold)),
                        ),
                    ],
                  ),
                  SizedBox(height: 8),
                  Text(
                    treatment['text'].length > 100
                        ? '${treatment['text'].substring(0, 100)}...'
                        : treatment['text'],
                    style: textTheme.bodySmall?.copyWith(height: 1.4),
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _buildMobileTreatmentHistory(BuildContext context, bool isDark) {
    final theme = Theme.of(context);
    final textTheme = theme.textTheme;
    if (_isLoadingTreatments) {
      return Center(
          child: CircularProgressIndicator(color: theme.primaryColor));
    }
    if (_treatmentHistory.isEmpty) {
      return _buildEmptyState(context, isDark);
    }
    return SizedBox(
      height: 200,
      child: ListView.builder(
        scrollDirection: Axis.horizontal,
        itemCount: _treatmentHistory.length,
        itemBuilder: (context, index) {
          final treatment = _treatmentHistory[index];
          final timestamp = DateTime.parse(treatment['timestamp']);
          final timeAgo = _getTimeAgo(timestamp);
          final isLatest = treatment['is_latest'] == true;
          return Container(
            width: 260,
            margin: EdgeInsets.only(right: 12),
            child: Card(
              elevation: isLatest ? 6 : 2,
              color: isLatest ? theme.primaryColor.withOpacity(0.05) : null,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
                side: isLatest
                    ? BorderSide(
                        color: theme.primaryColor.withOpacity(0.3), width: 2)
                    : BorderSide.none,
              ),
              child: Padding(
                padding: const EdgeInsets.all(12.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Icon(isLatest ? Icons.star : Icons.medical_services,
                            size: 16,
                            color:
                                isLatest ? Colors.amber : theme.primaryColor),
                        SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            isLatest ? 'Latest - $timeAgo' : timeAgo,
                            style: textTheme.bodySmall?.copyWith(
                                color: isLatest
                                    ? Colors.amber.shade700
                                    : theme.primaryColor,
                                fontWeight: FontWeight.w600),
                          ),
                        ),
                      ],
                    ),
                    SizedBox(height: 8),
                    Text(
                      treatment['text'].length > 90
                          ? '${treatment['text'].substring(0, 90)}...'
                          : treatment['text'],
                      style: textTheme.bodySmall?.copyWith(height: 1.4),
                    ),
                  ],
                ),
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _buildMetricsListView(BuildContext context, bool isDark) {
    final theme = Theme.of(context);
    final textTheme = theme.textTheme;
    return ListView.builder(
      itemCount: _organSystems.length,
      itemBuilder: (context, index) {
        final organ = _organSystems[index];
        return Padding(
          padding: const EdgeInsets.symmetric(vertical: 8.0),
          child: Card(
            elevation: 2,
            shape:
                RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            child: InkWell(
              onTap: () => _showPremiumDialog(context, organ),
              borderRadius: BorderRadius.circular(12),
              child: Padding(
                padding: const EdgeInsets.all(12.0),
                child: Row(
                  children: [
                    _getOrganIcon(organ),
                    SizedBox(width: 12),
                    Expanded(
                      child: Text(organ,
                          style: textTheme.bodyMedium
                              ?.copyWith(fontWeight: FontWeight.w600)),
                    ),
                    Container(
                      padding: EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                      decoration: BoxDecoration(
                        color: Colors.amber.withOpacity(0.2),
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: Colors.amber),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(Icons.star, size: 14, color: Colors.amber),
                          SizedBox(width: 4),
                          Text('Premium',
                              style: textTheme.bodySmall?.copyWith(
                                  color: Colors.amber.shade700,
                                  fontWeight: FontWeight.w600)),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _buildMobileMetricsList(BuildContext context, bool isDark) {
    final theme = Theme.of(context);
    final textTheme = theme.textTheme;
    return ListView.builder(
      shrinkWrap: true,
      physics: NeverScrollableScrollPhysics(),
      itemCount: _organSystems.length,
      itemBuilder: (context, index) {
        final organ = _organSystems[index];
        return Padding(
          padding: const EdgeInsets.symmetric(vertical: 6.0),
          child: Card(
            elevation: 2,
            shape:
                RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            child: InkWell(
              onTap: () => _showPremiumDialog(context, organ),
              borderRadius: BorderRadius.circular(12),
              child: Padding(
                padding: const EdgeInsets.all(12.0),
                child: Row(
                  children: [
                    _getOrganIcon(organ),
                    SizedBox(width: 12),
                    Expanded(
                      child: Text(organ,
                          style: textTheme.bodyMedium
                              ?.copyWith(fontWeight: FontWeight.w600)),
                    ),
                    Icon(Icons.chevron_right, color: theme.primaryColor),
                  ],
                ),
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _buildNotificationsList(BuildContext context, bool isDark) {
    final theme = Theme.of(context);
    final textTheme = theme.textTheme;
    if (_isLoadingNotifications) {
      return Center(
          child: CircularProgressIndicator(color: theme.primaryColor));
    }
    if (_notifications.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.notifications_none,
                size: 48, color: theme.colorScheme.onSurface.withOpacity(0.5)),
            SizedBox(height: 12),
            Text('No tasks or reminders yet',
                style: textTheme.bodyMedium?.copyWith(
                    color: theme.colorScheme.onSurface.withOpacity(0.7))),
          ],
        ),
      );
    }
    return ListView.builder(
      itemCount: _notifications.length,
      itemBuilder: (context, index) {
        final notification = _notifications[index];
        final createdAt = notification['created_at'] != null
            ? DateTime.tryParse(notification['created_at'].toString())
            : DateTime.now();
        final timeAgo = createdAt != null ? _getTimeAgo(createdAt) : 'Unknown';
        return Padding(
          padding: const EdgeInsets.symmetric(vertical: 8.0),
          child: Card(
            elevation: 2,
            shape:
                RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            child: Padding(
              padding: const EdgeInsets.all(12.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      _getNotificationIcon(notification['notification_type'] ??
                          'general_reminder'),
                      SizedBox(width: 12),
                      Expanded(
                          child: Text(notification['title'] ?? 'Reminder',
                              style: textTheme.bodyMedium
                                  ?.copyWith(fontWeight: FontWeight.w600))),
                      Container(
                        padding:
                            EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                        decoration: BoxDecoration(
                          color: _getPriorityColor(
                                  notification['priority'] ?? 'medium')
                              .withOpacity(0.1),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Text(
                          (notification['priority']
                                  ?.toString()
                                  .toUpperCase()) ??
                              'MEDIUM',
                          style: TextStyle(
                              fontSize: 10,
                              fontWeight: FontWeight.bold,
                              color: _getPriorityColor(
                                  notification['priority'] ?? 'medium')),
                        ),
                      ),
                    ],
                  ),
                  SizedBox(height: 8),
                  Text(notification['message'] ?? 'No description',
                      style: textTheme.bodySmall?.copyWith(
                          color: theme.colorScheme.onSurface.withOpacity(0.7))),
                  SizedBox(height: 8),
                  Row(
                    children: [
                      Icon(Icons.access_time,
                          size: 14, color: theme.primaryColor),
                      SizedBox(width: 4),
                      Text(timeAgo,
                          style: textTheme.bodySmall?.copyWith(
                              color: theme.primaryColor,
                              fontWeight: FontWeight.w500)),
                    ],
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _buildEmptyState(BuildContext context, bool isDark) {
    final theme = Theme.of(context);
    final textTheme = theme.textTheme;
    return Container(
      padding: EdgeInsets.all(32),
      decoration: BoxDecoration(
        color: theme.colorScheme.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: theme.colorScheme.outline.withOpacity(0.3)),
      ),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.history,
            size: 48,
            color: theme.colorScheme.onSurface.withOpacity(0.5),
          ),
          SizedBox(height: 16),
          Text(
            'No activity yet',
            style: textTheme.titleMedium?.copyWith(
              color: theme.colorScheme.onSurface.withOpacity(0.7),
            ),
          ),
          SizedBox(height: 8),
          Text(
            'Start chatting with your AI assistant to build your medical history',
            style: textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurface.withOpacity(0.5),
            ),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }

  Widget _buildMobileNotifications(BuildContext context, bool isDark) {
    return _buildNotificationsList(context, isDark);
  }
}
