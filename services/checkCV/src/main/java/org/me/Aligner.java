package org.me;

import nu.pattern.OpenCV;
import org.me.CheckUI.CheckFrame;
import org.me.ocr.OCRReader;
import org.opencv.core.*;
import org.opencv.imgcodecs.*;
import org.opencv.imgproc.CLAHE;
import org.opencv.imgproc.Imgproc;

import org.opencv.core.Point;

import java.io.File;
import java.util.*;

public class Aligner {
    static{
        OpenCV.loadLocally();
        System.out.println("OpenCV loaded");
    }

    public static byte[] align(byte[] imageBytes, int steps, String ext)
    {
        Mat mat = Imgcodecs.imdecode(new MatOfByte(imageBytes), Imgcodecs.IMREAD_COLOR);
        var maskBGR = findSamePixelFromCenterBGR(preprocess(mat));
        var polygon = maskToPolygon(maskBGR, steps);
        var p = preprocessForOCR(mat);
        Point[] corners = findMainCorners(polygon, 4).toArray();
        Point[] ordered = orderCornersTLTRBRBL(corners);
        double widthA = Math.hypot(ordered[1].x - ordered[0].x, ordered[1].y - ordered[0].y);
        double widthB = Math.hypot(ordered[2].x - ordered[3].x, ordered[2].y - ordered[3].y);
        double maxWidth = Math.max(widthA, widthB);
        double heightA = Math.hypot(ordered[3].x - ordered[0].x, ordered[3].y - ordered[0].y);
        double heightB = Math.hypot(ordered[2].x - ordered[1].x, ordered[2].y - ordered[1].y);
        double maxHeight = Math.max(heightA, heightB);
        maxWidth *= 1.5;
        maxHeight *= 1.5;
        Size outputSize = new Size(maxWidth, maxHeight);
        var warped = warpPolygonToRectangleSmart(p, polygon, outputSize);

        final MatOfByte mob = new MatOfByte();
        Imgcodecs.imencode(ext, warped, mob);
        return mob.toArray();
    }

    public void RunWithShow(Mat mat, int steps, CheckFrame view) throws InterruptedException {
        view.setImage(mat);
        view.setName("Normal");
        Thread.sleep(2000);
        var maskBGR = findSamePixelFromCenterBGR(preprocess(mat));
        view.setName("Mask BGR");
        view.setImage(maskBGR);
        Thread.sleep(2000);

        var polygon = maskToPolygon(maskBGR, steps);
        view.drawPolygon(mat, polygon, new Scalar(255, 200, 0), 5);
        view.setName("Polygon");
        Thread.sleep(2000);
        var p = preprocessForOCR(mat);
        view.setImage(p);
        view.setName("Preprocessed For OCR");
        Thread.sleep(2000);


        Point[] corners = findMainCorners(polygon, 4).toArray();
        Point[] ordered = orderCornersTLTRBRBL(corners);
        double widthA = Math.hypot(ordered[1].x - ordered[0].x, ordered[1].y - ordered[0].y);
        double widthB = Math.hypot(ordered[2].x - ordered[3].x, ordered[2].y - ordered[3].y);
        double maxWidth = Math.max(widthA, widthB);
        double heightA = Math.hypot(ordered[3].x - ordered[0].x, ordered[3].y - ordered[0].y);
        double heightB = Math.hypot(ordered[2].x - ordered[1].x, ordered[2].y - ordered[1].y);
        double maxHeight = Math.max(heightA, heightB);
        maxWidth *= 1.5;
        maxHeight *= 1.5;

        Size outputSize = new Size(maxWidth, maxHeight);

        var warped = warpPolygonToRectangleSmart(p, polygon, outputSize);
        view.setImage(warped);
        view.setName("Warped");
        System.out.println(warped.rows());
        System.out.println(warped.cols());
        final MatOfByte mob = new MatOfByte();
        Imgcodecs.imencode(".jpg", warped, mob);
        String text = OCRReader.readText(mob.toArray(), "rus").getText();
        System.out.println("📄 Распознанный текст:");
        System.out.println(text);
    }



    private static Mat preprocessForOCR(Mat src) {
        Mat gray = new Mat();
        Mat blur = new Mat();
        Mat thresh = new Mat();
        Mat morph = new Mat();
        Mat result = new Mat();

        // 1. Перевод в градации серого
        Imgproc.cvtColor(src, gray, Imgproc.COLOR_BGR2GRAY);

        // 2. Удаление шумов
        Imgproc.GaussianBlur(gray, blur, new Size(3, 3), 0);

        // 3. Адаптивная бинаризация (лучше чем фиксированный порог)
        Imgproc.adaptiveThreshold(
                blur,
                thresh,
                255,
                Imgproc.ADAPTIVE_THRESH_GAUSSIAN_C,
                Imgproc.THRESH_BINARY,
                31,  // размер блока
                10   // константа (сдвиг)
        );

        // 4. Морфологическая очистка (удаляем точки, дырки)
        Mat kernel = Imgproc.getStructuringElement(Imgproc.MORPH_RECT, new Size(1, 1));
        Imgproc.morphologyEx(thresh, morph, Imgproc.MORPH_OPEN, kernel);

        // 5. Усиление контраста (если OCR плохо видит серый текст)
        Core.normalize(morph, result, 0, 255, Core.NORM_MINMAX);

        return result;
    }

    // TL;DR: авто-порядок углов для warp = TL,TR,BR,BL,
// а для выпрямления — углы в порядке обхода контура.
    private static Mat warpPolygonToRectangleSmart(Mat image, MatOfPoint2f polygon, Size outputSize) {
        if (image == null || image.empty() || polygon == null || polygon.empty()) {
            System.out.println("⚠️ Пустое изображение или контур");
            return (image == null || image.empty()) ? new Mat() : image.clone();
        }

        // 1) находим 4 основные угла (если не вышло — minAreaRect)
        MatOfPoint2f simplified = findMainCorners(polygon, 4);
        Point[] corners = simplified.toArray();
        if (corners.length != 4) {
            System.out.println("⚠️ Не удалось выделить 4 угла — fallback minAreaRect");
            RotatedRect box = Imgproc.minAreaRect(polygon);
            Point[] rectPts = new Point[4];
            box.points(rectPts);
            corners = rectPts;
            simplified = new MatOfPoint2f(rectPts);
        }

        // 2) порядок углов для warp (TL, TR, BR, BL)
        Point[] warpOrder = orderCornersTLTRBRBL(corners);

        // 3) порядок углов в порядке обхода контура (для выпрямления промежуточных точек)
        Point[] contourOrder = cornersInContourOrder(polygon, corners);

        // 4) выпрямляем ВСЕ точки полигона по прямым между 4 углами (в порядке обхода)
        MatOfPoint2f straightened = straightenPolygonAlongContour(polygon, contourOrder);

        // (если нужно рисовать «ровный» полигон дальше — можно использовать straightened)
        // polygon.fromArray(straightened.toArray());

        // 5) целевой размер — из реальных сторон (если не задан)
        if (outputSize == null || outputSize.width <= 0 || outputSize.height <= 0) {
            double w = Math.max(dist(warpOrder[0], warpOrder[1]), dist(warpOrder[2], warpOrder[3]));
            double h = Math.max(dist(warpOrder[0], warpOrder[3]), dist(warpOrder[1], warpOrder[2]));
            double scale = 1.5;                    // лёгкое увеличение под OCR
            w = Math.max(64, Math.round(w * scale));
            h = Math.max(64, Math.round(h * scale));
            outputSize = new Size(w, h);
        }

        // 6) перспективное преобразование по 4 углам
        Point[] dst = new Point[] {
                new Point(0, 0),
                new Point(outputSize.width - 1, 0),
                new Point(outputSize.width - 1, outputSize.height - 1),
                new Point(0, outputSize.height - 1)
        };

        Mat H = Imgproc.getPerspectiveTransform(new MatOfPoint2f(warpOrder), new MatOfPoint2f(dst));
        Mat warped = new Mat();
        Imgproc.warpPerspective(image, warped, H, outputSize, Imgproc.INTER_CUBIC, Core.BORDER_REPLICATE);
        return warped;
    }

// ---------- helpers ----------

    // устойчивый порядок углов для warp: TL, TR, BR, BL
    private static Point[] orderCornersTLTRBRBL(Point[] pts) {
        Point tl = null, tr = null, br = null, bl = null;
        double minSum = Double.POSITIVE_INFINITY, maxSum = Double.NEGATIVE_INFINITY;
        double minDiff = Double.POSITIVE_INFINITY, maxDiff = Double.NEGATIVE_INFINITY;

        for (Point p : pts) {
            double sum = p.x + p.y;
            double diff = p.x - p.y;
            if (sum < minSum) { minSum = sum; tl = p; }
            if (sum > maxSum) { maxSum = sum; br = p; }
            if (diff > maxDiff) { maxDiff = diff; tr = p; }
            if (diff < minDiff) { minDiff = diff; bl = p; }
        }
        return new Point[]{ tl, tr, br, bl };
    }

    // углы в порядке обхода исходного контура (по индексам ближайших вершин)
    private static Point[] cornersInContourOrder(MatOfPoint2f polygon, Point[] corners) {
        Point[] poly = polygon.toArray();
        int n = poly.length;

        // ищем индексы ближайших точек контура к каждому углу
        int[] idx = new int[corners.length];
        for (int i = 0; i < corners.length; i++) {
            idx[i] = closestIndex(poly, corners[i]);
        }

        // нормализуем, начиная с минимального индекса
        Integer[] order = new Integer[]{0,1,2,3};
        Arrays.sort(order, Comparator.comparingInt(i -> idx[i]));
        Point[] out = new Point[4];
        for (int k = 0; k < 4; k++) out[k] = corners[order[k]];
        return out; // теперь [C0,C1,C2,C3] идут вдоль контура
    }

    private static int closestIndex(Point[] poly, Point target) {
        int best = 0;
        double bestD = Double.POSITIVE_INFINITY;
        for (int i = 0; i < poly.length; i++) {
            double d = dist(poly[i], target);
            if (d < bestD) { bestD = d; best = i; }
        }
        return best;
    }

    private static double dist(Point a, Point b) {
        return Math.hypot(a.x - b.x, a.y - b.y);
    }

    // «выпрямление» полигональной границы: все точки между Ck и Ck+1 проецируем на прямую [Ck,Ck+1]
    private static MatOfPoint2f straightenPolygonAlongContour(MatOfPoint2f polygon, Point[] cornersContourOrder) {
        Point[] poly = polygon.toArray();
        int n = poly.length;

        // индексы углов в контуре
        int i0 = closestIndex(poly, cornersContourOrder[0]);
        int i1 = closestIndex(poly, cornersContourOrder[1]);
        int i2 = closestIndex(poly, cornersContourOrder[2]);
        int i3 = closestIndex(poly, cornersContourOrder[3]);

        // обходим всегда вперёд по контуру (с циклическим переходом)
        List<Point> out = new ArrayList<>(n);

        // четыре дуги контура: [i0->i1], [i1->i2], [i2->i3], [i3->i0]
        projectArc(poly, i0, i1, cornersContourOrder[0], cornersContourOrder[1], out);
        projectArc(poly, i1, i2, cornersContourOrder[1], cornersContourOrder[2], out);
        projectArc(poly, i2, i3, cornersContourOrder[2], cornersContourOrder[3], out);
        projectArc(poly, i3, i0, cornersContourOrder[3], cornersContourOrder[0], out);

        return new MatOfPoint2f(out.toArray(new Point[0]));
    }

    private static void projectArc(Point[] poly, int from, int to, Point A, Point B, List<Point> dst) {
        int n = poly.length;
        int i = from;
        do {
            dst.add(projectPointOnSegment(poly[i], A, B));
            i = (i + 1) % n;
        } while (i != to);
        // включаем конечную точку дуги
        dst.add(projectPointOnSegment(poly[to], A, B));
    }

    // ортогональная проекция точки на отрезок AB
    private static Point projectPointOnSegment(Point P, Point A, Point B) {
        double vx = B.x - A.x, vy = B.y - A.y;
        double len2 = vx*vx + vy*vy;
        if (len2 == 0) return new Point(A.x, A.y);
        double t = ((P.x - A.x)*vx + (P.y - A.y)*vy) / len2;
        t = Math.max(0.0, Math.min(1.0, t));
        return new Point(A.x + t*vx, A.y + t*vy);
    }


    private static MatOfPoint2f findMainCorners(MatOfPoint2f polygon, int count) {
        Point[] pts = polygon.toArray();
        if (pts.length <= count) return polygon;

        List<PointWithAngle> angles = new ArrayList<>();

        for (int i = 0; i < pts.length; i++) {
            Point prev = pts[(i - 1 + pts.length) % pts.length];
            Point curr = pts[i];
            Point next = pts[(i + 1) % pts.length];

            double angle = Math.abs(Math.toDegrees(
                    Math.atan2(next.y - curr.y, next.x - curr.x) -
                            Math.atan2(prev.y - curr.y, prev.x - curr.x)
            ));
            if (angle > 180) angle = 360 - angle;
            angles.add(new PointWithAngle(curr, angle));
        }

        // Берём точки с наименьшими углами (резкие повороты — углы чека)
        angles.sort(Comparator.comparingDouble(a -> a.angle));
        List<Point> result = new ArrayList<>();
        for (int i = 0; i < Math.min(count, angles.size()); i++) {
            result.add(angles.get(i).point);
        }

        return new MatOfPoint2f(result.toArray(new Point[0]));
    }

    private static class PointWithAngle {
        Point point;
        double angle;
        PointWithAngle(Point p, double a) {
            point = p; angle = a;
        }
    }

    private static MatOfPoint2f maskToPolygon(Mat mask, double simplifyStep) {
        // 1️⃣ Морфологическая очистка (твоя, я оставил)
        Mat clean = new Mat();
        Mat kernel = Imgproc.getStructuringElement(Imgproc.MORPH_RECT, new Size(5, 5));
        Imgproc.morphologyEx(mask, clean, Imgproc.MORPH_CLOSE, kernel);
        Imgproc.morphologyEx(clean, clean, Imgproc.MORPH_OPEN, kernel);
        Imgproc.morphologyEx(clean, clean, Imgproc.MORPH_CLOSE,
                Imgproc.getStructuringElement(Imgproc.MORPH_RECT, new Size(15, 15)));
        Imgproc.morphologyEx(clean, clean, Imgproc.MORPH_OPEN,
                Imgproc.getStructuringElement(Imgproc.MORPH_RECT, new Size(5, 5)));

        // 2️⃣ Находим контуры
        List<MatOfPoint> contours = new ArrayList<>();
        Mat hierarchy = new Mat();
        Imgproc.findContours(clean, contours, hierarchy, Imgproc.RETR_EXTERNAL, Imgproc.CHAIN_APPROX_NONE);

        if (contours.isEmpty()) {
            System.out.println("⚠️ Контуры не найдены");
            return new MatOfPoint2f();
        }

        // 3️⃣ Самый большой контур
        MatOfPoint bestContour = contours.stream()
                .max((a, b) -> Double.compare(Imgproc.contourArea(a), Imgproc.contourArea(b)))
                .orElse(null);

        if (bestContour == null) return new MatOfPoint2f();

        // 4️⃣ Аппроксимация с адаптивным epsilon
        MatOfPoint2f contour2f = new MatOfPoint2f(bestContour.toArray());
        double peri = Imgproc.arcLength(contour2f, true);
        MatOfPoint2f approx = new MatOfPoint2f();
        double epsilon = simplifyStep > 0 ? simplifyStep : 0.02 * peri;
        Imgproc.approxPolyDP(contour2f, approx, epsilon, true);

        // 5️⃣ Фильтрация острых углов
        approx = filterSharpAngles(approx, 15);

        // 6️⃣ Если после фильтра контур сильно изломан — берём minAreaRect (идеальный прямоугольник)
        if (approx.rows() < 4 || approx.rows() > 8) {
            RotatedRect box = Imgproc.minAreaRect(contour2f);
            Point[] rectPts = new Point[4];
            box.points(rectPts);
            approx = new MatOfPoint2f(rectPts);
        }

        return approx;
    }
    private static MatOfPoint2f filterSharpAngles(MatOfPoint2f polygon, double minAngleDeg) {
        List<Point> filtered = new ArrayList<>();
        Point[] pts = polygon.toArray();

        for (int i = 0; i < pts.length; i++) {
            Point prev = pts[(i - 1 + pts.length) % pts.length];
            Point curr = pts[i];
            Point next = pts[(i + 1) % pts.length];

            double angle = Math.abs(Math.toDegrees(
                    Math.atan2(next.y - curr.y, next.x - curr.x) -
                            Math.atan2(prev.y - curr.y, prev.x - curr.x)
            ));
            if (angle < 0) angle += 360;
            // Пропускаем точки с "острым" углом (< minAngleDeg)
            if (angle > minAngleDeg && angle < (360 - minAngleDeg)) {
                filtered.add(curr);
            }
        }

        return new MatOfPoint2f(filtered.toArray(new Point[0]));
    }

    private static Mat preprocess(Mat image) {
        Mat processed = new Mat();

        // Сглаживаем шум (Gaussian Blur)
        Imgproc.GaussianBlur(image, processed, new Size(5, 5), 0);

        // Переводим в LAB — лучше работает с освещением, чем BGR
        Imgproc.cvtColor(processed, processed, Imgproc.COLOR_BGR2Lab);

        // Выровнять освещённость (CLAHE на L-канале)
        List<Mat> lab = new ArrayList<>();
        Core.split(processed, lab);
        CLAHE clahe = Imgproc.createCLAHE(1.5, new Size(8, 8));
        clahe.apply(lab.get(0), lab.get(0));
        Core.merge(lab, processed);

        // Возвращаем в BGR
        Imgproc.cvtColor(processed, processed, Imgproc.COLOR_Lab2BGR);

        // Немного повышаем контраст
        Core.addWeighted(processed, 1.2, new Mat(processed.size(), processed.type(), new Scalar(0, 0, 0)), 0, 0, processed);

        return processed;
    }

    private static List<Mat> loadImages(String folderName)
    {
        List<Mat> mats = new LinkedList<>();
        File folder = new File(folderName);
        File[] files = folder.listFiles((dir, name) ->
                name.toLowerCase().endsWith(".jpg")
                        || name.toLowerCase().endsWith(".jpeg")
                        || name.toLowerCase().endsWith(".png")
                        || name.toLowerCase().endsWith(".bmp")
                        || name.toLowerCase().endsWith(".tif")
                        || name.toLowerCase().endsWith(".tiff")
        );

        if (files == null || files.length == 0) {
            System.out.println("В папке нет изображений!");
            return mats;
        }

        for (File file : files) {
            Mat image = Imgcodecs.imread(file.getAbsolutePath());
            if (!image.empty()) {
                mats.add(image);
                System.out.println("Загружено: " + file.getName());
            } else {
                System.out.println("Не удалось прочитать: " + file.getName());
            }
        }
        return mats;
    }

    private static Mat findSamePixelFromCenterBGR(Mat image) {
        image = image.clone();
        int rows = image.rows();
        int cols = image.cols();
        Point center = new Point(cols / 2, rows / 2);

        List<double[]> samples = getSamples(image, center);
        double[] meanColor = getMeanColor(samples);
        double tolerance = computeAutoToleranceBGR(samples, meanColor);
        double[] fillColor = new double[]{255, 0, 255};
        boolean[][] visited = new boolean[rows][cols];

        // поиск в ширину
        Queue<Point> queue = new LinkedList<>();
        queue.add(center);
        visited[(int) center.y][(int) center.x] = true;
        int[][] dirs = {{1,0}, {-1,0}, {0,1}, {0,-1}, {1,1}, {-1,-1}, {1,-1}, {-1,1}};
        Mat mask = Mat.zeros(rows, cols, CvType.CV_8UC1);

        while (!queue.isEmpty()) {
            Point p = queue.poll();
            double[] color = image.get((int) p.y, (int) p.x);
            if (color == null) continue;

            if (colorDistance(color, meanColor) <= tolerance) {
                double alpha = 0.005; // скорость адаптации (0.0–1.0)
                for (int c = 0; c < 3; c++) {
                    meanColor[c] = meanColor[c] * (1 - alpha) + color[c] * alpha;
                }
                mask.put((int) p.y, (int) p.x, 255);
                for (int[] d : dirs) {
                    int ny = (int) p.y + d[1];
                    int nx = (int) p.x + d[0];
                    if (nx >= 0 && ny >= 0 && nx < cols && ny < rows && !visited[ny][nx]) {
                        visited[ny][nx] = true;
                        queue.add(new Point(nx, ny));
                    }
                }
            }
        }
        return mask;
    }

    private static double computeAutoToleranceBGR(List<double[]> samples, double[] meanColor) {
        // Локальный разброс (variance)
        double variance = 0.0;
        for (double[] s : samples) {
            variance += colorDistance(s, meanColor);
        }
        variance /= samples.size();

        // Средняя яркость (по формуле 0.299R + 0.587G + 0.114B)
        double brightness = meanColor[2] * 0.299 + meanColor[1] * 0.587 + meanColor[0] * 0.114;

        // Автоматическая толерантность:
        // - чем темнее изображение → тем выше tolerance
        // - чем выше variance → тем выше tolerance
        double tolerance = 13 + (255 - brightness) * 0.7 + variance * 0.7;

        // Ограничим диапазон
        tolerance = Math.max(10, Math.min(65, tolerance));

        return tolerance;
    }

    private static double[] getMeanColor(List<double[]> samples) {
        double[] meanColor = {0, 0, 0};
        for (double[] c : samples) {
            meanColor[0] += c[0];
            meanColor[1] += c[1];
            meanColor[2] += c[2];
        }
        meanColor[0] /= samples.size();
        meanColor[1] /= samples.size();
        meanColor[2] /= samples.size();
        return meanColor;
    }

    private static List<double[]> getSamples(Mat image, Point center){
        return getSamples(image, center, 2);
    }

    private static List<double[]> getSamples(Mat image, Point center, int sampleRadius) {
        List<double[]> samples = new ArrayList<>();
        for (int dy = -sampleRadius; dy <= sampleRadius; dy++) {
            for (int dx = -sampleRadius; dx <= sampleRadius; dx++) {
                double[] color = image.get((int) center.y + dy, (int) center.x + dx);
                if (color != null) samples.add(color);
            }
        }
        return samples;
    }

    private static double colorDistance(double[] a, double[] b) {
        double db = a[0] - b[0];
        double dg = a[1] - b[1];
        double dr = a[2] - b[2];
        return Math.sqrt(db * db + dg * dg + dr * dr);
    }
}