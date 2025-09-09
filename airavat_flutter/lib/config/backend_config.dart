class BackendConfig {
  static const String baseUrl =
      'https://airavat-backend-f255cpkfda-uc.a.run.app';
  static const String apiUrl = '$baseUrl/agent';

  // API Endpoints
  static const String queryEndpoint = '$apiUrl/query';
  static const String feedbackEndpoint = '$apiUrl/feedback';
  static const String memoryEndpoint = '$apiUrl/memory';
  static const String treatmentPlanEndpoint = '$apiUrl/update_treatment_plan';
  static const String healthEndpoint = '$baseUrl/health';
}
