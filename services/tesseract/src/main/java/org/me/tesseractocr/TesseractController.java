package org.me.tesseractocr;
import org.me.ocr.OCRResult;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

@RestController
@RequestMapping("/recognize")
public class TesseractController {

    @PostMapping(consumes = MediaType.MULTIPART_FORM_DATA_VALUE,
            produces = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<OCRResult> recognize(
            @RequestParam("file") MultipartFile file,
            @RequestParam(defaultValue = "rus") String lang)
    {

        try {
            OCRResult result = ServiceTesseract.ocr(file.getBytes(), lang);
            return ResponseEntity.ok(result);
        } catch (Exception e) {
            e.printStackTrace();
            return ResponseEntity.internalServerError().build();
        }
    }
}
