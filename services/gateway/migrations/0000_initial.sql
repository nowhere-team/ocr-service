CREATE TYPE "public"."engine_enum" AS ENUM('tesseract', 'paddleocr');--> statement-breakpoint
CREATE TYPE "public"."qr_format_enum" AS ENUM('fiscal', 'url', 'unknown');--> statement-breakpoint
CREATE TYPE "public"."result_type_enum" AS ENUM('text', 'qr');--> statement-breakpoint
CREATE TYPE "public"."status_enum" AS ENUM('queued', 'processing', 'completed', 'failed');--> statement-breakpoint
CREATE TABLE "images" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"original_url" varchar(512) NOT NULL,
	"processed_url" varchar(512),
	"file_size" integer NOT NULL,
	"mime_Type" varchar(50) NOT NULL,
	"width" integer,
	"height" integer,
	"source_service" varchar(50),
	"source_reference" varchar(128),
	"uploaded_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "recognition_results" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"image_id" uuid NOT NULL,
	"status" "status_enum" DEFAULT 'queued' NOT NULL,
	"result_type" "result_type_enum",
	"raw_text" text,
	"confidence" numeric(3, 2),
	"engine" "engine_enum",
	"aligned" boolean DEFAULT false,
	"qr_data" text,
	"qr_format" "qr_format_enum",
	"qr_location" jsonb,
	"processing_time" integer,
	"queue_wait_time" integer,
	"attempt_number" integer DEFAULT 1 NOT NULL,
	"error" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"completed_at" timestamp with time zone
);
--> statement-breakpoint
ALTER TABLE "recognition_results" ADD CONSTRAINT "recognition_results_image_id_images_id_fk" FOREIGN KEY ("image_id") REFERENCES "public"."images"("id") ON DELETE cascade ON UPDATE no action;