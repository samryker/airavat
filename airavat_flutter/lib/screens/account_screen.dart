// lib/screens/account_screen.dart

import 'package:flutter/material.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:go_router/go_router.dart';

class AccountScreen extends StatefulWidget {
  @override
  _AccountScreenState createState() => _AccountScreenState();
}

class _AccountScreenState extends State<AccountScreen> {
  final _formKey = GlobalKey<FormState>();
  final user = FirebaseAuth.instance.currentUser!;

  // Profile fields
  String? bmiIndex;
  String medicines = '';
  String allergies = '';
  String history = '';
  String goal = '';
  int? age;
  String? race;
  String? gender;

  // Habits options
  final List<String> _habitOptions = [
    'Smoking',
    'Unsafe Sex',
    'Alcohol Abuse',
    'Teetotaler',
    'Drug Use',
    'Sugary Foods'
  ];
  final Set<String> _selectedHabits = {};

  Future<void> _saveProfile() async {
    if (!_formKey.currentState!.validate()) return;
    _formKey.currentState!.save();

    await FirebaseFirestore.instance.collection('patients').doc(user.uid).set({
      'email': user.email,
      'bmiIndex': bmiIndex,
      'medicines': medicines,
      'allergies': allergies,
      'history': history,
      'goal': goal,
      'age': age,
      'race': race,
      'gender': gender,
      'habits': _selectedHabits.toList(),
      'updatedAt': FieldValue.serverTimestamp(),
    }, SetOptions(merge: true));

    // Transition via GoRouter
    context.go('/dashboard');
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Account')),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Form(
          key: _formKey,
          child: ListView(
            children: [
              // Show email
              Text('Email: ${user.email}'),
              SizedBox(height: 16),

              // BMI dropdown
              DropdownButtonFormField<String>(
                decoration: InputDecoration(labelText: 'BMI Index'),
                items: ['Underweight', 'Normal', 'Overweight', 'Obese']
                    .map((e) => DropdownMenuItem(value: e, child: Text(e)))
                    .toList(),
                onChanged: (v) => bmiIndex = v,
                validator: (v) => v == null ? 'Please select BMI' : null,
              ),
              SizedBox(height: 16),

              // Medicines
              TextFormField(
                decoration: InputDecoration(labelText: 'Current Medicines'),
                onSaved: (v) => medicines = v ?? '',
              ),
              SizedBox(height: 16),

              // Allergies
              TextFormField(
                decoration: InputDecoration(labelText: 'Allergies'),
                onSaved: (v) => allergies = v ?? '',
              ),
              SizedBox(height: 16),

              // Health history
              TextFormField(
                decoration: InputDecoration(labelText: 'Health History'),
                onSaved: (v) => history = v ?? '',
              ),
              SizedBox(height: 16),

              // Goal
              TextFormField(
                decoration: InputDecoration(labelText: 'Goal'),
                onSaved: (v) => goal = v ?? '',
              ),
              SizedBox(height: 16),

              // Age
              TextFormField(
                decoration: InputDecoration(labelText: 'Age'),
                keyboardType: TextInputType.number,
                onSaved: (v) => age = int.tryParse(v ?? ''),
              ),
              SizedBox(height: 16),

              // Race
              DropdownButtonFormField<String>(
                decoration: InputDecoration(labelText: 'Race/Descent'),
                items: ['Asian', 'Black', 'White', 'Hispanic', 'Other']
                    .map((e) => DropdownMenuItem(value: e, child: Text(e)))
                    .toList(),
                onChanged: (v) => race = v,
                validator: (v) => v == null ? 'Please select race' : null,
              ),
              SizedBox(height: 16),

              // Gender
              DropdownButtonFormField<String>(
                decoration: InputDecoration(labelText: 'Gender'),
                items: ['Male', 'Female', 'Other']
                    .map((e) => DropdownMenuItem(value: e, child: Text(e)))
                    .toList(),
                onChanged: (v) => gender = v,
                validator: (v) => v == null ? 'Please select gender' : null,
              ),
              SizedBox(height: 24),

              // Habits
              Text('Habits', style: Theme.of(context).textTheme.subtitle1),
              ..._habitOptions.map((habit) {
                return CheckboxListTile(
                  value: _selectedHabits.contains(habit),
                  title: Text(habit),
                  onChanged: (checked) {
                    setState(() {
                      if (checked == true)
                        _selectedHabits.add(habit);
                      else
                        _selectedHabits.remove(habit);
                    });
                  },
                );
              }).toList(),
              SizedBox(height: 24),

              // Save button
              ElevatedButton(
                onPressed: _saveProfile,
                child: Text('Save & Continue'),
                style: ElevatedButton.styleFrom(
                  minimumSize: Size(double.infinity, 48),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
