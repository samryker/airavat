// lib/screens/sign_up_screen.dart
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:firebase_auth/firebase_auth.dart';
// import 'package:google_fonts/google_fonts.dart'; // Import Google Fonts - REMOVED

class SignUpScreen extends StatefulWidget {
  @override
  _SignUpScreenState createState() => _SignUpScreenState();
}

class _SignUpScreenState extends State<SignUpScreen> {
  final _formKey = GlobalKey<FormState>();
  String _email = '', _password = '', _confirm = '';
  bool _loading = false;
  String? _errorMessage; // For displaying persistent errors

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _loading = true;
      _errorMessage = null; // Clear previous errors
    });
    try {
      await FirebaseAuth.instance
          .createUserWithEmailAndPassword(email: _email, password: _password);
      if (mounted) context.go('/onboarding1');
    } on FirebaseAuthException catch (e) {
      setState(() {
        _errorMessage = e.message ?? 'An unknown error occurred.';
      });
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    // final screenHeight = MediaQuery.of(context).size.height; // Not strictly needed without complex responsive font sizes

    return Scaffold(
      body: SafeArea(
        child: Center(
          // Center the content
          child: SingleChildScrollView(
            // Allow scrolling on smaller screens
            padding:
                const EdgeInsets.symmetric(horizontal: 24.0, vertical: 32.0),
            child: ConstrainedBox(
              // Constrain width for larger screens
              constraints: const BoxConstraints(maxWidth: 400),
              child: Column(
                mainAxisAlignment:
                    MainAxisAlignment.center, // Center vertically too
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(
                    'Create Account',
                    style: textTheme.headlineMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                        fontFamily: 'sans-serif'), // Using default sans-serif
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Start your Airavat journey today.',
                    style: textTheme.titleSmall?.copyWith(
                        fontFamily: 'sans-serif'), // Using default sans-serif
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 32),
                  Card(
                    // Wrap form in a Card
                    elevation: 5,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(16),
                    ),
                    child: Padding(
                      padding: const EdgeInsets.all(24.0),
                      child: Form(
                        key: _formKey,
                        child: Column(
                          children: [
                            TextFormField(
                              decoration: InputDecoration(
                                labelText: 'Email Address',
                                hintText: 'you@example.com',
                                prefixIcon: const Icon(Icons.email_outlined),
                                border: OutlineInputBorder(
                                  borderRadius: BorderRadius.circular(12),
                                ),
                                filled: true,
                                fillColor: Colors.grey[50],
                              ),
                              keyboardType: TextInputType.emailAddress,
                              style: textTheme.bodyMedium?.copyWith(
                                  fontFamily:
                                      'sans-serif'), // Using default sans-serif
                              onChanged: (v) => _email = v.trim(),
                              validator: (v) {
                                if (v == null || v.trim().isEmpty)
                                  return 'Please enter your email.';
                                if (!v.trim().contains('@') ||
                                    !v.trim().contains('.'))
                                  return 'Enter a valid email address.';
                                return null;
                              },
                            ),
                            const SizedBox(height: 16),
                            TextFormField(
                              decoration: InputDecoration(
                                labelText: 'Password',
                                hintText: 'Enter your password',
                                prefixIcon: const Icon(Icons.lock_outline),
                                border: OutlineInputBorder(
                                  borderRadius: BorderRadius.circular(12),
                                ),
                                filled: true,
                                fillColor: Colors.grey[50],
                              ),
                              obscureText: true,
                              style: textTheme.bodyMedium?.copyWith(
                                  fontFamily:
                                      'sans-serif'), // Using default sans-serif
                              onChanged: (v) => _password = v,
                              validator: (v) {
                                if (v == null || v.isEmpty)
                                  return 'Please enter a password.';
                                if (v.length < 6)
                                  return 'Password must be at least 6 characters.';
                                return null;
                              },
                            ),
                            const SizedBox(height: 16),
                            TextFormField(
                              decoration: InputDecoration(
                                labelText: 'Confirm Password',
                                hintText: 'Re-enter your password',
                                prefixIcon: const Icon(Icons.lock_outline),
                                border: OutlineInputBorder(
                                  borderRadius: BorderRadius.circular(12),
                                ),
                                filled: true,
                                fillColor: Colors.grey[50],
                              ),
                              obscureText: true,
                              style: textTheme.bodyMedium?.copyWith(
                                  fontFamily:
                                      'sans-serif'), // Using default sans-serif
                              onChanged: (v) => _confirm = v,
                              validator: (v) {
                                if (v == null || v.isEmpty)
                                  return 'Please confirm your password.';
                                if (v != _password)
                                  return 'Passwords do not match.';
                                return null;
                              },
                            ),
                            const SizedBox(height: 24),
                            if (_errorMessage != null) // Display error message
                              Padding(
                                padding: const EdgeInsets.only(bottom: 16.0),
                                child: Text(
                                  _errorMessage!,
                                  style: TextStyle(
                                      color:
                                          Theme.of(context).colorScheme.error,
                                      fontSize: 14,
                                      fontFamily:
                                          'sans-serif'), // Using default sans-serif
                                  textAlign: TextAlign.center,
                                ),
                              ),
                            ElevatedButton(
                              onPressed: _loading ? null : _submit,
                              style: ElevatedButton.styleFrom(
                                padding:
                                    const EdgeInsets.symmetric(vertical: 16),
                                minimumSize: const Size(
                                    double.infinity, 50), // Full width button
                                shape: RoundedRectangleBorder(
                                  borderRadius: BorderRadius.circular(12),
                                ),
                                backgroundColor: Theme.of(context)
                                    .primaryColor, // Use theme color
                                foregroundColor: Colors.white, // Text color
                              ),
                              child: _loading
                                  ? const SizedBox(
                                      width: 24,
                                      height: 24,
                                      child: CircularProgressIndicator(
                                          color: Colors.white,
                                          strokeWidth: 2.5),
                                    )
                                  : Text('Sign Up',
                                      style: textTheme.labelLarge?.copyWith(
                                          fontFamily: 'sans-serif',
                                          color: Colors.white,
                                          fontWeight: FontWeight
                                              .bold)), // Using default sans-serif
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 24),
                  TextButton(
                    onPressed: _loading ? null : () => context.go('/login'),
                    child: Text.rich(
                      TextSpan(
                        text: 'Already have an account? ',
                        style: textTheme.bodyMedium?.copyWith(
                            fontFamily:
                                'sans-serif'), // Using default sans-serif
                        children: [
                          TextSpan(
                            text: 'Log In',
                            style: textTheme.bodyMedium?.copyWith(
                                color: Theme.of(context).primaryColor,
                                fontWeight: FontWeight.bold,
                                fontFamily:
                                    'sans-serif' // Using default sans-serif
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
        ),
      ),
    );
  }
}
