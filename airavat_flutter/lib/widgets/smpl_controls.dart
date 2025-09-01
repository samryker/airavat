import 'package:flutter/material.dart';

class SmplControls extends StatefulWidget {
  final void Function(
      {String? gender, double? height, double? weight, double? beta1}) onChange;
  const SmplControls({super.key, required this.onChange});

  @override
  State<SmplControls> createState() => _SmplControlsState();
}

class _SmplControlsState extends State<SmplControls> {
  String _gender = 'neutral';
  double _height = 170;
  double _weight = 70;
  double _beta1 = 0.4;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(12.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                DropdownButton<String>(
                  value: _gender,
                  items: const [
                    DropdownMenuItem(value: 'neutral', child: Text('Neutral')),
                    DropdownMenuItem(value: 'male', child: Text('Male')),
                    DropdownMenuItem(value: 'female', child: Text('Female')),
                  ],
                  onChanged: (v) {
                    if (v == null) return;
                    setState(() => _gender = v);
                    widget.onChange(
                        gender: v,
                        height: _height,
                        weight: _weight,
                        beta1: _beta1);
                  },
                ),
                const SizedBox(width: 12),
                Text('SMPL',
                    style: theme.textTheme.titleMedium
                        ?.copyWith(fontWeight: FontWeight.w600)),
              ],
            ),
            const SizedBox(height: 8),
            _buildSlider(
              label: 'Height (cm): ${_height.toStringAsFixed(0)}',
              value: _height,
              min: 140,
              max: 200,
              onChanged: (v) {
                setState(() => _height = v);
                widget.onChange(
                    gender: _gender, height: v, weight: _weight, beta1: _beta1);
              },
            ),
            _buildSlider(
              label: 'Weight (kg): ${_weight.toStringAsFixed(0)}',
              value: _weight,
              min: 45,
              max: 120,
              onChanged: (v) {
                setState(() => _weight = v);
                widget.onChange(
                    gender: _gender, height: _height, weight: v, beta1: _beta1);
              },
            ),
            _buildSlider(
              label: 'Beta1: ${_beta1.toStringAsFixed(2)}',
              value: _beta1,
              min: 0,
              max: 1,
              onChanged: (v) {
                setState(() => _beta1 = v);
                widget.onChange(
                    gender: _gender,
                    height: _height,
                    weight: _weight,
                    beta1: v);
              },
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSlider(
      {required String label,
      required double value,
      required double min,
      required double max,
      required ValueChanged<double> onChanged}) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label),
        Slider(value: value, min: min, max: max, onChanged: onChanged),
      ],
    );
  }
}
