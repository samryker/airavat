// lib/main.dart
import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/material.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:go_router/go_router.dart';
import 'firebase_options.dart';

import 'screens/splash.dart';
import 'screens/signup_screen.dart';
import 'screens/login_screen.dart';
import 'screens/account_screen.dart';
import 'screens/onboarding_screen1.dart';
import 'screens/onboarding_screen2.dart';
import 'screens/onboarding_screen3.dart';
import 'screens/dashboard_screen.dart';
import 'screens/chat_page.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Firebase.initializeApp(
    options: DefaultFirebaseOptions.currentPlatform,
  );
  runApp(DigitalTwinApp());
}

class DigitalTwinApp extends StatelessWidget {
  final GoRouter _router = GoRouter(
    initialLocation: '/splash',
    routes: [
      GoRoute(path: '/splash', builder: (_, __) => SplashScreen()),
      GoRoute(path: '/signup', builder: (_, __) => SignUpScreen()),
      GoRoute(path: '/login', builder: (_, __) => LoginScreen()),
      GoRoute(path: '/account', builder: (_, __) => AccountScreen()),
      GoRoute(path: '/onboarding1', builder: (_, __) => Onboarding1Screen()),
      GoRoute(path: '/onboarding2', builder: (_, __) => Onboarding2Screen()),
      GoRoute(path: '/onboarding3', builder: (_, __) => Onboarding3Screen()),
      GoRoute(path: '/dashboard', builder: (_, __) => DashboardScreen()),
      GoRoute(path: '/chat', builder: (_, __) => ChatPage()),
    ],
    // Redirect after sign-up/login to /account:
    redirect: (context, state) {
      final loggedIn = FirebaseAuth.instance.currentUser != null;
      final goingToAuth = state.matchedLocation == '/login' ||
          state.matchedLocation == '/signup';
      if (!loggedIn && !goingToAuth && state.matchedLocation != '/splash') {
        return '/login';
      }
      return null;
    },
  );

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: 'Digital Twin',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF1E3A8A),
          secondary: const Color(0xFFF59E0B),
        ),
        scaffoldBackgroundColor: Colors.white,
        fontFamily: 'Roboto',
      ),
      routerConfig: _router,
    );
  }
}
