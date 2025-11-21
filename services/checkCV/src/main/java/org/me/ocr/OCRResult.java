package org.me.ocr;

public class OCRResult {
    private String text;
    private float confidence;

    public OCRResult(String text, float confidence) {
        this.text = text;
        this.confidence = confidence;
    }

    public String getText() {
        return text;
    }

    public float getConfidence() {
        return confidence;
    }
}