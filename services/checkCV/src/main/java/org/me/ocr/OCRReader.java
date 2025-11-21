package org.me.ocr;

import org.bytedeco.leptonica.PIX;
import org.bytedeco.javacpp.BytePointer;
import org.bytedeco.tesseract.TessBaseAPI;
import org.opencv.core.Mat;
import org.opencv.core.MatOfByte;
import org.opencv.imgcodecs.Imgcodecs;

import static org.bytedeco.leptonica.global.leptonica.*;

public class OCRReader {

    public static OCRResult readText(byte[] imageBytes, String lang) {
        TessBaseAPI api = new TessBaseAPI();
        BytePointer outText = null;
        String result = "";
        float confidence = -1f;
        Mat mat = Imgcodecs.imdecode(new MatOfByte(imageBytes), Imgcodecs.IMREAD_COLOR);

        try {
            String tempPath = System.getProperty("java.io.tmpdir") + "/ocr_temp.png";
            Imgcodecs.imwrite(tempPath, mat);
            PIX image = pixRead(tempPath);

            String tessdataPath = System.getenv("TESSDATA_PATH");
            if (tessdataPath == null || tessdataPath.isEmpty()) {
                tessdataPath = "/opt/homebrew/share/tessdata";
            }

            if (api.Init(tessdataPath, lang) != 0) {
                System.err.println("Не удалось инициализировать Tesseract OCR.");
                return new OCRResult("", 0f);
            }

            api.SetPageSegMode(3);
            api.SetImage(image);

            outText = api.GetUTF8Text();
            result = outText.getString().trim();
            confidence = api.MeanTextConf();

            api.End();
            pixDestroy(image);
        } catch (Exception e) {
            e.printStackTrace();
        } finally {
            if (outText != null) outText.deallocate();
        }

        return new OCRResult(result, confidence);
    }
}
