package org.me.CheckUI;

import org.opencv.core.*;
import org.opencv.core.Point;
import org.opencv.imgcodecs.Imgcodecs;
import org.opencv.imgproc.Imgproc;

import javax.swing.*;
import java.awt.*;
import java.util.List;

public class CheckFrame extends JFrame {
    JLabel imageView = new JLabel();
    JLabel nameView = new JLabel();
    public CheckFrame(){
        JPanel verticalPanel = new JPanel();
        verticalPanel.setLayout(new BoxLayout(verticalPanel, BoxLayout.Y_AXIS));
        setVisible(true);
        nameView.setBounds(0,0,100,20);
        imageView.setBounds(10,0,1000,1000);
        verticalPanel.add(nameView);
        verticalPanel.add(imageView);
        add(verticalPanel);
    }

    public void setImage(Mat image)
    {
        final MatOfByte mob = new MatOfByte();
        Imgcodecs.imencode(".jpg", image, mob);
        ImageIcon icon = new ImageIcon(mob.toArray());
        if(icon.getIconWidth()>600 || icon.getIconHeight()>600){
            double multiplier = (double) 600 / Math.max(icon.getIconWidth(), icon.getIconHeight());
            icon = new ImageIcon(icon.getImage().getScaledInstance(
                            (int) Math.round(icon.getIconWidth() * multiplier),
                            (int) Math.round(icon.getIconHeight() * multiplier),
                            Image.SCALE_DEFAULT));
        }
        setSize(icon.getIconWidth()+20, icon.getIconHeight()+20);
        imageView.setBounds(10,10,icon.getIconWidth(), icon.getIconHeight());
        imageView.setIcon(icon);
    }

    public void setName(String name)
    {
        nameView.setText(name);
    }


    public void drawPolygon(Mat image, MatOfPoint2f polygon, Scalar color, int thickness) {
        image = image.clone();
        if (polygon == null || polygon.empty()) {
            setImage(image);
            return;
        }

        Mat result = image.clone();
        MatOfPoint poly = new MatOfPoint(polygon.toArray());

        // Нарисуем контур
        Imgproc.polylines(result, List.of(poly), true, color, thickness);

        // Добавим точки
        for (Point p : polygon.toArray()) {
            Imgproc.circle(result, p, 4, new Scalar(0, 255, 0), -1);
        }

        setImage(result);
    }

}
