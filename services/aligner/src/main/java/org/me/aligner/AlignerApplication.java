package org.me.aligner;

import nu.pattern.OpenCV;
import org.me.Aligner;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class AlignerApplication {
    static {
        OpenCV.loadLocally();
    }

    public static void main(String[] args) {
        SpringApplication.run(AlignerApplication.class, args);
    }

}
