package org.me.aligner;

import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

@RestController
public class AlignerController {

    @PostMapping(value = "/align", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<byte[]> align(@RequestParam("file") MultipartFile file) {
        try {
            byte[] aligned = AlignService.align(file.getBytes());
            return ResponseEntity.ok()
                    .header(HttpHeaders.CONTENT_DISPOSITION, "inline; filename=\"aligned.jpg\"")
                    .contentType(MediaType.IMAGE_JPEG)
                    .body(aligned);
        } catch (Exception e) {
            return ResponseEntity.internalServerError()
                    .contentType(MediaType.TEXT_PLAIN)
                    .body(("Ошибка обработки: " + e.getMessage()).getBytes());
        }
    }
}
