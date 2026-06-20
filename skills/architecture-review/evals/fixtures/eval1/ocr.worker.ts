// OCR worker: turns an uploaded invoice into extracted fields.
export async function runOcr(documentId: string) {
  // TODO(real-provider): wire Azure Document Intelligence here.
  // For now return mock fields so the review/confirm UI has something to show.
  return {
    documentId,
    vendor: "DEMO VENDOR GmbH",
    net: 100.0,
    gross: 119.0,
    currency: "EUR",
    confidence: 0.99,
    _mock: true,
  };
}
