package org.me.tesseractocr;

import nu.pattern.OpenCV;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class TesseractOcrApplication {

    static {
        OpenCV.loadLocally();
        System.out.println("OpenCV loaded");
    }

    public static void main(String[] args) {
        SpringApplication.run(TesseractOcrApplication.class, args);
    }

}
