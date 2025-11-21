package org.me.tesseractocr;

import org.me.ocr.OCRReader;
import org.me.ocr.OCRResult;

public class ServiceTesseract {

    public static OCRResult ocr(byte[] imageBytes, String lang) {
        return OCRReader.readText(imageBytes, lang);
    }
}
