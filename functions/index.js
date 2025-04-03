const { onRequest } = require("firebase-functions/v2/https");
const { onDocumentCreated, onDocumentUpdated } = require("firebase-functions/v2/firestore");
const admin = require("firebase-admin");
admin.initializeApp();

// Trigger when new biomarker report is added
exports.onNewReport = onDocumentCreated('biomarkers/{patientId}/reports/{reportId}', async (event) => {
  const newData = event.data;
  const patientId = event.params.patientId;

  // Sample logic: if hemoglobin < 9.5, create alert
  if (newData.hemoglobin < 9.5) {
    await admin.firestore()
      .collection('alerts')
      .doc(patientId)
      .set({
        alertType: "Low Hemoglobin",
        value: newData.hemoglobin,
        timestamp: admin.firestore.FieldValue.serverTimestamp()
      });
  }

  return null;
});

