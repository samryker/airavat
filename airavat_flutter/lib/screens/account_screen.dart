// lib/screens/account_screen.dart

import 'package:flutter/material.dart';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:go_router/go_router.dart';

class AccountScreen extends StatefulWidget {
  @override
  _AccountScreenState createState() => _AccountScreenState();
}

// Helper class for Treatment Plan
class TreatmentPlan {
  String treatmentName;
  String? condition;
  DateTime? startDate;
  DateTime? endDate;
  String? status;

  TreatmentPlan({
    this.treatmentName = '',
    this.condition,
    this.startDate,
    this.endDate,
    this.status,
  });

  Map<String, dynamic> toMap() {
    return {
      'treatmentName': treatmentName,
      'condition': condition,
      'startDate': startDate != null ? Timestamp.fromDate(startDate!) : null,
      'endDate': endDate != null ? Timestamp.fromDate(endDate!) : null,
      'status': status,
    };
  }
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

  // Treatment Plan fields
  List<TreatmentPlan> _treatmentPlans = [
    TreatmentPlan()
  ]; // Start with one empty plan

  Future<void> _saveProfile() async {
    if (!_formKey.currentState!.validate()) return;
    _formKey.currentState!.save();

    // Filter out incomplete treatment plans
    List<TreatmentPlan> validTreatmentPlans = _treatmentPlans
        .where((plan) =>
            plan.treatmentName.isNotEmpty &&
            (plan.condition != null ||
                plan.status != null ||
                plan.startDate != null))
        .toList();

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
      'treatmentPlans': validTreatmentPlans
          .map((plan) => plan.toMap())
          .toList(), // Save treatment plans
      'updatedAt': FieldValue.serverTimestamp(),
    }, SetOptions(merge: true));

    // Transition via GoRouter
    if (mounted) context.go('/dashboard');
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

  Widget _buildTreatmentPlanCard(int index) {
    final plan = _treatmentPlans[index];
    final textTheme = Theme.of(context).textTheme;

    return Card(
      elevation: 3, // Consistent elevation
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12), // Consistent border radius
      ),
      margin: const EdgeInsets.symmetric(vertical: 8.0),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text('Treatment Plan ${index + 1}',
                    style: textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w600, fontFamily: 'sans-serif')),
                if (index > 0) // Allow removing only if not the first one
                  IconButton(
                    icon: Icon(Icons.remove_circle_outline,
                        color: Colors.red.shade300),
                    tooltip: 'Remove Plan',
                    onPressed: () {
                      setState(() {
                        _treatmentPlans.removeAt(index);
                      });
                    },
                  ),
              ],
            ),
            const SizedBox(height: 12),
            TextFormField(
              initialValue: plan.treatmentName,
              decoration: _inputDecoration('Treatment Name',
                  hintText: 'e.g., Chemotherapy, Insulin Therapy'),
              style: textTheme.bodyMedium?.copyWith(fontFamily: 'sans-serif'),
              onSaved: (v) => plan.treatmentName = v ?? '',
              validator: (v) {
                // Validate only if other fields are filled or it's the only plan and it has some text
                bool otherFieldsFilled = plan.condition != null ||
                    plan.status != null ||
                    plan.startDate != null;
                if ((otherFieldsFilled || _treatmentPlans.length == 1) &&
                    (v == null || v.isEmpty)) {
                  return 'Please enter a treatment name or remove this plan.';
                }
                return null;
              },
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              value: plan.condition,
              decoration: _inputDecoration('Condition/Illness (if applicable)'),
              style: textTheme.bodyMedium?.copyWith(fontFamily: 'sans-serif'),
              items: [
                'Cancer - Breast',
                'Cancer - Lung',
                'Cancer - Prostate',
                'Cancer - Colorectal',
                'Cancer - Melanoma',
                'Cancer - Leukemia',
                'Cancer - Lymphoma',
                'Diabetes Type 1',
                'Diabetes Type 2',
                'Hypertension',
                'Heart Disease',
                'Asthma',
                'Arthritis',
                'Chronic Kidney Disease',
                'Other Cancer',
                'Other Chronic Illness'
              ]
                  .map((e) => DropdownMenuItem(
                      value: e,
                      child: Text(e,
                          style: textTheme.bodyMedium
                              ?.copyWith(fontFamily: 'sans-serif'))))
                  .toList(),
              onChanged: (v) => setState(() => plan.condition = v),
              onSaved: (v) => plan.condition = v,
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: InkWell(
                    onTap: () async {
                      DateTime? pickedDate = await showDatePicker(
                        context: context,
                        initialDate: plan.startDate ?? DateTime.now(),
                        firstDate: DateTime(2000),
                        lastDate: DateTime(2101),
                      );
                      if (pickedDate != null) {
                        setState(() {
                          plan.startDate = pickedDate;
                        });
                      }
                    },
                    child: InputDecorator(
                      decoration: _inputDecoration('Start Date').copyWith(
                        hintText: plan.startDate == null ? 'Select date' : null,
                      ),
                      child: Text(
                        plan.startDate == null
                            ? 'Select date'
                            : '${plan.startDate!.toLocal()}'.split(' ')[0],
                        style: textTheme.bodyMedium
                            ?.copyWith(fontFamily: 'sans-serif'),
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: InkWell(
                    onTap: () async {
                      DateTime? pickedDate = await showDatePicker(
                        context: context,
                        initialDate:
                            plan.endDate ?? plan.startDate ?? DateTime.now(),
                        firstDate: plan.startDate ?? DateTime(2000),
                        lastDate: DateTime(2101),
                      );
                      if (pickedDate != null) {
                        setState(() {
                          plan.endDate = pickedDate;
                        });
                      }
                    },
                    child: InputDecorator(
                      decoration:
                          _inputDecoration('End Date (Optional)').copyWith(
                        hintText: plan.endDate == null ? 'Select date' : null,
                      ),
                      child: Text(
                        plan.endDate == null
                            ? 'Select date'
                            : '${plan.endDate!.toLocal()}'.split(' ')[0],
                        style: textTheme.bodyMedium
                            ?.copyWith(fontFamily: 'sans-serif'),
                      ),
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              value: plan.status,
              decoration: _inputDecoration('Status'),
              style: textTheme.bodyMedium?.copyWith(fontFamily: 'sans-serif'),
              items: ['Planned', 'Ongoing', 'Completed', 'Paused', 'Cancelled']
                  .map((e) => DropdownMenuItem(
                      value: e,
                      child: Text(e,
                          style: textTheme.bodyMedium
                              ?.copyWith(fontFamily: 'sans-serif'))))
                  .toList(),
              onChanged: (v) => setState(() => plan.status = v),
              onSaved: (v) => plan.status = v,
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    return Scaffold(
      appBar: AppBar(
        title: Text('Your Health Profile',
            style: textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.bold, fontFamily: 'sans-serif')),
        centerTitle: true,
        elevation: 1,
      ),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Form(
          key: _formKey,
          child: ListView(
            children: [
              _buildSectionTitle('Personal Information', textTheme),
              Text('Email: ${user.email}',
                  style: textTheme.bodyMedium?.copyWith(
                      fontFamily: 'sans-serif', color: Colors.grey.shade700)),
              const SizedBox(height: 16),

              DropdownButtonFormField<String>(
                decoration: _inputDecoration('BMI Index',
                    prefixIcon: Icons.accessibility_new),
                style: textTheme.bodyMedium?.copyWith(fontFamily: 'sans-serif'),
                items: ['Underweight', 'Normal', 'Overweight', 'Obese']
                    .map((e) => DropdownMenuItem(
                        value: e,
                        child: Text(e,
                            style: textTheme.bodyMedium
                                ?.copyWith(fontFamily: 'sans-serif'))))
                    .toList(),
                onChanged: (v) => bmiIndex = v,
                validator: (v) => v == null ? 'Please select BMI' : null,
              ),
              const SizedBox(height: 12),
              TextFormField(
                decoration: _inputDecoration('Current Medicines',
                    hintText: 'e.g., Aspirin, Metformin (comma-separated)',
                    prefixIcon: Icons.medical_services_outlined),
                style: textTheme.bodyMedium?.copyWith(fontFamily: 'sans-serif'),
                onSaved: (v) => medicines = v ?? '',
              ),
              const SizedBox(height: 12),
              TextFormField(
                decoration: _inputDecoration('Allergies',
                    hintText: 'e.g., Peanuts, Penicillin (comma-separated)',
                    prefixIcon: Icons.do_not_touch_outlined),
                style: textTheme.bodyMedium?.copyWith(fontFamily: 'sans-serif'),
                onSaved: (v) => allergies = v ?? '',
              ),
              const SizedBox(height: 12),
              TextFormField(
                decoration: _inputDecoration('Significant Health History',
                    prefixIcon: Icons.history_edu_outlined),
                style: textTheme.bodyMedium?.copyWith(fontFamily: 'sans-serif'),
                onSaved: (v) => history = v ?? '',
                maxLines: 3,
                minLines: 1,
              ),
              const SizedBox(height: 12),
              TextFormField(
                decoration: _inputDecoration('Health Goal',
                    hintText: 'e.g., manage condition, improve fitness',
                    prefixIcon: Icons.flag_outlined),
                style: textTheme.bodyMedium?.copyWith(fontFamily: 'sans-serif'),
                onSaved: (v) => goal = v ?? '',
              ),
              const SizedBox(height: 12),
              TextFormField(
                decoration:
                    _inputDecoration('Age', prefixIcon: Icons.cake_outlined),
                style: textTheme.bodyMedium?.copyWith(fontFamily: 'sans-serif'),
                keyboardType: TextInputType.number,
                onSaved: (v) => age = int.tryParse(v ?? ''),
                validator: (v) {
                  if (v == null || v.isEmpty) return 'Please enter age';
                  if (int.tryParse(v) == null)
                    return 'Please enter a valid number';
                  return null;
                },
              ),
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                decoration: _inputDecoration('Race/Descent',
                    prefixIcon: Icons.public_outlined),
                style: textTheme.bodyMedium?.copyWith(fontFamily: 'sans-serif'),
                items: ['Asian', 'Black', 'White', 'Hispanic', 'Other']
                    .map((e) => DropdownMenuItem(
                        value: e,
                        child: Text(e,
                            style: textTheme.bodyMedium
                                ?.copyWith(fontFamily: 'sans-serif'))))
                    .toList(),
                onChanged: (v) => race = v,
                validator: (v) => v == null ? 'Please select race' : null,
              ),
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                decoration:
                    _inputDecoration('Gender', prefixIcon: Icons.wc_outlined),
                style: textTheme.bodyMedium?.copyWith(fontFamily: 'sans-serif'),
                items: ['Male', 'Female', 'Other']
                    .map((e) => DropdownMenuItem(
                        value: e,
                        child: Text(e,
                            style: textTheme.bodyMedium
                                ?.copyWith(fontFamily: 'sans-serif'))))
                    .toList(),
                onChanged: (v) => gender = v,
                validator: (v) => v == null ? 'Please select gender' : null,
              ),
              const SizedBox(height: 24),

              _buildSectionTitle('Lifestyle Habits', textTheme),
              ..._habitOptions.map((habit) {
                return CheckboxListTile(
                  value: _selectedHabits.contains(habit),
                  title: Text(habit,
                      style: textTheme.bodyMedium
                          ?.copyWith(fontFamily: 'sans-serif')),
                  onChanged: (checked) {
                    setState(() {
                      if (checked == true)
                        _selectedHabits.add(habit);
                      else
                        _selectedHabits.remove(habit);
                    });
                  },
                  activeColor: Theme.of(context).primaryColor,
                  controlAffinity: ListTileControlAffinity.leading,
                  contentPadding: EdgeInsets.zero,
                );
              }).toList(),
              const SizedBox(height: 24),

              _buildSectionTitle('Existing Treatment Plans', textTheme),
              Text(
                'Add any current or past major treatment plans, for conditions like cancer, diabetes, heart disease, etc.',
                style: textTheme.bodySmall?.copyWith(
                    fontFamily: 'sans-serif', color: Colors.grey.shade600),
              ),
              const SizedBox(height: 8),
              ListView.builder(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                itemCount: _treatmentPlans.length,
                itemBuilder: (context, index) {
                  return _buildTreatmentPlanCard(index);
                },
              ),
              const SizedBox(height: 16),
              TextButton.icon(
                icon: Icon(Icons.add_circle_outline,
                    color: Theme.of(context).primaryColor),
                label: Text('Add Another Treatment Plan',
                    style: textTheme.labelLarge?.copyWith(
                        fontFamily: 'sans-serif',
                        color: Theme.of(context).primaryColor,
                        fontWeight: FontWeight.bold)),
                style: TextButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(8)),
                ),
                onPressed: () {
                  setState(() {
                    _treatmentPlans.add(TreatmentPlan());
                  });
                },
              ),
              const SizedBox(height: 32),

              ElevatedButton.icon(
                icon: const Icon(Icons.save_alt_outlined),
                label: Text('Save & Continue',
                    style: textTheme.labelLarge?.copyWith(
                        fontFamily: 'sans-serif',
                        color: Colors.white,
                        fontWeight: FontWeight.bold)),
                onPressed: _saveProfile,
                style: ElevatedButton.styleFrom(
                  minimumSize: const Size(double.infinity, 50),
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  backgroundColor: Theme.of(context).primaryColor,
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                  elevation: 3,
                ),
              ),
              const SizedBox(height: 16), // Added some bottom padding
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildSectionTitle(String title, TextTheme textTheme) {
    return Padding(
      padding: const EdgeInsets.only(top: 8.0, bottom: 12.0),
      child: Text(
        title,
        style: textTheme.headlineSmall?.copyWith(
            fontWeight: FontWeight.w600,
            fontFamily: 'sans-serif',
            color: Theme.of(context).primaryColorDark),
      ),
    );
  }
}
