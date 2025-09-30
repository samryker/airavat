class BackendConfig {
  static const String baseUrl =
      'https://airavat-backend-10892877764.us-central1.run.app';
  static const String apiUrl = '$baseUrl/agent';

  // Legacy API Endpoints (for backward compatibility)
  static const String queryEndpoint = '$apiUrl/query';
  static const String feedbackEndpoint = '$apiUrl/feedback';
  static const String memoryEndpoint = '$apiUrl/memory';
  static const String treatmentPlanEndpoint = '$apiUrl/update_treatment_plan';
  static const String healthEndpoint = '$baseUrl/health';

  // New Optimized API Endpoints
  static const String geminiSuggestEndpoint = '$baseUrl/gemini/suggest';
  static const String uploadAnalyzeEndpoint = '$baseUrl/upload/analyze';
  static const String costEstimateEndpoint = '$baseUrl/cost/estimate';
  static const String geneticAnalyzeEndpoint = '$baseUrl/genetic/analyze';
  static const String debugConfigEndpoint = '$baseUrl/debug/config';
}
