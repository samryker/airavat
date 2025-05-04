// lib/screens/onboarding3_screen.dart
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:lottie/lottie.dart';

class Onboarding3Screen extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 24),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.center,
              mainAxisSize: MainAxisSize.min,
              children: [
                Lottie.asset('assets/animations/onboard3.json', height: 200),
                SizedBox(height: 32),
                Text(
                  'Get Insights',
                  style: theme.textTheme.headline5,
                  textAlign: TextAlign.center,
                ),
                SizedBox(height: 16),
                Text(
                  'Receive AI-driven treatment simulations and alerts.',
                  textAlign: TextAlign.center,
                ),
                SizedBox(height: 32),
                ElevatedButton(
                  onPressed: () => context.go('/account'),
                  child: Text('Continue'),
                  style: ElevatedButton.styleFrom(
                    minimumSize: Size(150, 48),
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(8)),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
