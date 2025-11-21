package org.me.aligner;

import org.me.Aligner;

public class AlignService {
    public static byte[] align(byte[] imageBytes) {
        byte[] result = Aligner.align(imageBytes, 50, ".jpg");

        return result;
    }
}