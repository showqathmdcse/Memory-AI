# Spring Boot Gateway

API Gateway service built with Spring Boot that routes requests to the Python agent service.

## Prerequisites

- Java 17+
- Maven 3.6+ (or use Maven Wrapper if available)

## Setup

### Option 1: Using Maven (if installed)

```bash
# Build the project
mvn clean install

# Run the application
mvn spring-boot:run
```

### Option 2: Using IDE

1. Open the project in IntelliJ IDEA or Eclipse
2. Build the project
3. Run `com.development.Main` class

### Option 3: Install Maven

**macOS with Admin Access:**
```bash
brew install maven
```

**Without Admin Access:**
Download Maven manually from https://maven.apache.org/download.cgi and add to PATH

## Running the Service

The service will start on `http://localhost:8080`

## API Endpoints

- `POST /api/chat` - Forward chat requests to Python agent service
- Configured to proxy to `http://localhost:8000` (Python service)

## Configuration

Edit `src/main/resources/application.properties` to configure:
- Server port
- Python service URL
- CORS settings
- Other Spring Boot configurations

## Project Structure

```
src/
├── main/
│   ├── java/com/development/
│   │   ├── Main.java                  # Application entry point
│   │   ├── controller/
│   │   │   └── ChatController.java    # REST API endpoints
│   │   └── tools/
│   │       └── ToolRegistry.java      # Tool definitions
│   └── resources/
│       └── application.properties     # Configuration
```

## Note

Maven wrapper files (mvnw, mvnw.cmd) are missing from the project. You'll need to install Maven separately or generate the wrapper using:
```bash
mvn wrapper:wrapper
