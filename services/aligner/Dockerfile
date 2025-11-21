# ---------- Этап 1: сборка ----------
# --- build stage ---
FROM maven:3.9.6-eclipse-temurin-17 AS builder
WORKDIR /app

# Копируем pom + внешний jar и регистрируем его в локальном .m2
COPY pom.xml .
COPY CheckCV-1.0.jar /tmp/CheckCV-1.0.jar
RUN mvn -q -e install:install-file \
    -Dfile=/tmp/CheckCV-1.0.jar \
    -DgroupId=org.me \
    -DartifactId=check-align \
    -Dversion=1.0 \
    -Dpackaging=jar

# Теперь копируем исходники и собираем
COPY src ./src
RUN mvn clean package -DskipTests

# ---------- Этап 2: рантайм ----------
FROM eclipse-temurin:17-jdk
WORKDIR /app

# Скопировать собранный jar из builder’а
COPY --from=builder /app/target/*.jar app.jar

# nu.pattern.OpenCV сам разархивирует нативные .so/.dylib/.dll в /tmp
ENV OPENCV_OPENCV_PATH=/tmp
ENV JAVA_OPTS=""

# Экспонируем порт приложения
EXPOSE 9090

# Запуск Spring Boot
ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS -jar app.jar"]
#ENTRYPOINT ["top", "-b"]