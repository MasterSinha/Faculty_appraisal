# Spring Boot Migration Guide

Audience: backend developers performing the FastAPI → Spring Boot rewrite.  
This document is a living reference — update it as decisions are made.

---

## Table of Contents

1. [Why this document exists](#1-why-this-document-exists)
2. [What does NOT change](#2-what-does-not-change)
3. [Technology mapping](#3-technology-mapping)
4. [Maven dependencies](#4-maven-dependencies)
5. [Target project structure](#5-target-project-structure)
6. [File-by-file migration map](#6-file-by-file-migration-map)
7. [Key implementation patterns](#7-key-implementation-patterns)
8. [Environment variables](#8-environment-variables)
9. [Database and migrations](#9-database-and-migrations)
10. [Deployment changes](#10-deployment-changes)
11. [Migration phases](#11-migration-phases)
12. [Testing strategy](#12-testing-strategy)
13. [Risks and gotchas](#13-risks-and-gotchas)

---

## 1. Why this document exists

The current backend is FastAPI (Python). A future migration to Spring Boot (Java) is planned. This document captures every assumption, mapping, and decision needed so the migration team can work without reverse-engineering the existing codebase from scratch.

**Do not start the migration until:**
- The React frontend (`admin_ui/`) is feature-complete and stable
- The main faculty-facing frontend is feature-complete and stable
- The PostgreSQL schema has been stable for at least one full appraisal cycle
- Both devs are free to focus on this full-time

---

## 2. What does NOT change

These things are entirely independent of the backend language and carry over with zero rework:

| Item | Notes |
|---|---|
| PostgreSQL database schema | `Docs/schema.sql` is already the source of truth. Tables, indexes, constraints, and triggers are all reusable. |
| SQL migration files | `migrations/NNN_*.sql` are plain SQL and database-agnostic. Run them on the same DB instance. |
| API contracts | `Docs/frontend_api_reference.md` defines every endpoint, request shape, and response shape. Spring Boot must match these exactly — any deviation breaks the frontends. |
| JWT token format | If you use the same `JWT_SECRET_KEY` and HS256 algorithm, existing tokens remain valid across the cutover. |
| React admin dashboard (`admin_ui/`) | Calls `/api/v1/*` on the same origin. No frontend changes needed. |
| Main faculty frontend | Same — calls the same endpoints documented in `Docs/frontend_api_reference.md`. |
| Environment variable names | Keep the same names. Only the loading mechanism changes (Python `dotenv` → Spring `application.yml` / `@Value`). |
| Google Cloud Run deployment | Spring Boot Docker images are supported on Cloud Run without any infrastructure changes. |
| GCS bucket | Same bucket, same paths. Only the client library changes (Python GCS SDK → Java GCS SDK). |

---

## 3. Technology mapping

| Concern | FastAPI (current) | Spring Boot (target) |
|---|---|---|
| Web framework | FastAPI | Spring Boot + Spring MVC |
| Async model | Python asyncio / `async def` | Spring MVC (blocking, thread-per-request) — simpler, acceptable for this scale |
| ORM | SQLAlchemy (async) | Spring Data JPA + Hibernate |
| DB driver | asyncpg | PostgreSQL JDBC driver |
| Request validation | Pydantic v2 | Bean Validation (Jakarta) — `@Valid`, `@NotNull`, `@Size`, etc. |
| Auth | Custom JWT (`pyjwt`) + bcrypt (`passlib`) | Spring Security + `jjwt` (Java JWT) + BCryptPasswordEncoder |
| Role-based access | Custom `has_authority_over()` in `dependencies.py` | Custom `GrantedAuthority` or `@PreAuthorize` expressions |
| Dependency injection | FastAPI `Depends()` | Spring `@Autowired` / constructor injection |
| Exception handling | Custom `AppError` + `@app.exception_handler` | `@ControllerAdvice` + `@ExceptionHandler` |
| Email | `fastapi-mail` (SMTP) | Spring Mail (`JavaMailSender`) |
| File storage | `storage_utils.py` (local or GCS) | Custom `StorageService` bean (local or GCS Java SDK) |
| Admin web UI | `sqladmin` (Python) | Dropped — the React `admin_ui/` panel replaces it fully |
| Config management | `python-dotenv` + `os.getenv` | `application.yml` + `@ConfigurationProperties` |
| CORS | FastAPI `CORSMiddleware` | Spring Security CORS config |
| Static file serving | Starlette `StaticFiles` mount | Spring MVC `ResourceHandlerRegistry` |
| Testing | `pytest` + `pytest-asyncio` | JUnit 5 + Spring Boot Test + Mockito |
| Build / run | `uvicorn` / `gunicorn` | Embedded Tomcat (default) or Undertow |
| Package manager | `pyproject.toml` / `uv` | Maven (`pom.xml`) or Gradle (`build.gradle`) |

**Recommendation:** Use Maven. It is more widely documented for Spring Boot and easier to debug dependency conflicts than Gradle for teams new to the ecosystem.

---

## 4. Maven dependencies

Paste this block into `pom.xml`. Versions are current as of mid-2025 — check [mvnrepository.com](https://mvnrepository.com) for updates before starting.

```xml
<parent>
  <groupId>org.springframework.boot</groupId>
  <artifactId>spring-boot-starter-parent</artifactId>
  <version>3.3.0</version>
</parent>

<properties>
  <java.version>21</java.version>
</properties>

<dependencies>

  <!-- Web -->
  <dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-web</artifactId>
  </dependency>

  <!-- Security (JWT auth, CORS, role checks) -->
  <dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-security</artifactId>
  </dependency>

  <!-- JPA + Hibernate -->
  <dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-data-jpa</artifactId>
  </dependency>

  <!-- PostgreSQL JDBC driver -->
  <dependency>
    <groupId>org.postgresql</groupId>
    <artifactId>postgresql</artifactId>
    <scope>runtime</scope>
  </dependency>

  <!-- Bean Validation -->
  <dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-validation</artifactId>
  </dependency>

  <!-- JWT — JJWT library -->
  <dependency>
    <groupId>io.jsonwebtoken</groupId>
    <artifactId>jjwt-api</artifactId>
    <version>0.12.5</version>
  </dependency>
  <dependency>
    <groupId>io.jsonwebtoken</groupId>
    <artifactId>jjwt-impl</artifactId>
    <version>0.12.5</version>
    <scope>runtime</scope>
  </dependency>
  <dependency>
    <groupId>io.jsonwebtoken</groupId>
    <artifactId>jjwt-jackson</artifactId>
    <version>0.12.5</version>
    <scope>runtime</scope>
  </dependency>

  <!-- Email -->
  <dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-mail</artifactId>
  </dependency>

  <!-- Google Cloud Storage (for document uploads) -->
  <dependency>
    <groupId>com.google.cloud</groupId>
    <artifactId>google-cloud-storage</artifactId>
    <version>2.40.0</version>
  </dependency>

  <!-- Cloud SQL Java connector (replaces Unix socket path used by asyncpg) -->
  <dependency>
    <groupId>com.google.cloud.sql</groupId>
    <artifactId>postgres-socket-factory</artifactId>
    <version>1.19.0</version>
  </dependency>

  <!-- Lombok (reduces boilerplate — getters, setters, constructors) -->
  <dependency>
    <groupId>org.projectlombok</groupId>
    <artifactId>lombok</artifactId>
    <optional>true</optional>
  </dependency>

  <!-- Testing -->
  <dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-test</artifactId>
    <scope>test</scope>
  </dependency>
  <dependency>
    <groupId>org.springframework.security</groupId>
    <artifactId>spring-security-test</artifactId>
    <scope>test</scope>
  </dependency>

</dependencies>
```

---

## 5. Target project structure

```
src/
└── main/
    ├── java/
    │   └── com/dyp/appraisal/
    │       ├── AppraisalApplication.java       ← @SpringBootApplication entry point
    │       │
    │       ├── config/
    │       │   ├── SecurityConfig.java         ← Spring Security, JWT filter, CORS
    │       │   ├── JwtConfig.java              ← JWT secret, expiry from application.yml
    │       │   ├── StorageConfig.java          ← GCS client bean / local toggle
    │       │   └── MailConfig.java             ← JavaMailSender bean
    │       │
    │       ├── security/
    │       │   ├── JwtTokenProvider.java       ← create / verify JWT tokens
    │       │   ├── JwtAuthFilter.java          ← OncePerRequestFilter, populates SecurityContext
    │       │   ├── UserPrincipal.java          ← implements UserDetails, holds role/school/dept
    │       │   └── RoleHierarchy.java          ← has_authority_over() logic
    │       │
    │       ├── exception/
    │       │   ├── AppException.java           ← equivalent of AppError (user_message + detail)
    │       │   ├── GlobalExceptionHandler.java ← @ControllerAdvice, formats all errors
    │       │   └── ErrorResponse.java          ← { user_message, detail } DTO
    │       │
    │       ├── entity/                         ← JPA entities (one per DB table)
    │       │   ├── core/
    │       │   │   ├── FacultyProfile.java
    │       │   │   ├── Declaration.java
    │       │   │   ├── AppraisalSnapshot.java  ← JSONB column needs special handling (see §7)
    │       │   │   ├── AppraisalReview.java
    │       │   │   ├── AppraisalDocument.java
    │       │   │   ├── AppraisalConfig.java
    │       │   │   ├── Announcement.java
    │       │   │   ├── Feedback.java
    │       │   │   └── FormSectionDefinition.java
    │       │   ├── parta/
    │       │   │   ├── BasePartAEntity.java    ← @MappedSuperclass with common score cols
    │       │   │   ├── TeachingProcess.java
    │       │   │   ├── CourseFile.java
    │       │   │   ├── InnovativeTeaching.java
    │       │   │   ├── ProjectGuided.java
    │       │   │   ├── QualificationEnhancement.java
    │       │   │   ├── StudentFeedback.java
    │       │   │   ├── DepartmentActivity.java
    │       │   │   ├── UniversityActivity.java
    │       │   │   ├── SocialContribution.java
    │       │   │   ├── IndustryConnect.java
    │       │   │   └── AcrScore.java
    │       │   └── partb/
    │       │       ├── BasePartBEntity.java
    │       │       ├── JournalPublication.java
    │       │       ├── BookPublication.java
    │       │       ├── IctPedagogy.java
    │       │       ├── ResearchGuidance.java
    │       │       ├── ResearchProject.java
    │       │       ├── ExternalResearchProject.java
    │       │       ├── Patent.java
    │       │       ├── Award.java
    │       │       ├── Conference.java
    │       │       ├── ResearchProposal.java
    │       │       ├── ProductDeveloped.java
    │       │       ├── SelfDevelopment.java
    │       │       └── IndustrialTraining.java
    │       │
    │       ├── repository/                     ← Spring Data JPA repositories (one per entity)
    │       │   ├── core/
    │       │   │   ├── FacultyProfileRepository.java
    │       │   │   ├── DeclarationRepository.java
    │       │   │   ├── AppraisalSnapshotRepository.java
    │       │   │   ├── AppraisalReviewRepository.java
    │       │   │   ├── AppraisalConfigRepository.java
    │       │   │   └── AnnouncementRepository.java
    │       │   ├── parta/
    │       │   │   └── (one per Part A entity)
    │       │   └── partb/
    │       │       └── (one per Part B entity)
    │       │
    │       ├── dto/                            ← Request and response objects (Pydantic schemas → DTOs)
    │       │   ├── auth/
    │       │   │   ├── LoginRequest.java
    │       │   │   ├── LoginResponse.java
    │       │   │   ├── RegisterRequest.java
    │       │   │   └── ChangePasswordRequest.java
    │       │   ├── appraisal/
    │       │   │   ├── SnapshotRequest.java
    │       │   │   ├── SubmitRequest.java
    │       │   │   └── AppraisalStatusResponse.java
    │       │   ├── admin/
    │       │   │   ├── StatsResponse.java
    │       │   │   ├── UserCreateRequest.java
    │       │   │   ├── UserUpdateRequest.java
    │       │   │   └── AppraisalConfigRequest.java
    │       │   ├── dashboard/
    │       │   │   └── SubordinateRow.java
    │       │   └── announcement/
    │       │       ├── AnnouncementRequest.java
    │       │       └── AnnouncementResponse.java
    │       │
    │       ├── service/                        ← Business logic (CRUD layer + appraisal logic)
    │       │   ├── AuthService.java
    │       │   ├── UserService.java
    │       │   ├── AppraisalService.java       ← contains shredForm() — most complex class
    │       │   ├── DashboardService.java
    │       │   ├── RemarksService.java
    │       │   ├── AdminService.java
    │       │   ├── AnnouncementService.java
    │       │   ├── FeedbackService.java
    │       │   ├── StorageService.java         ← local/GCS toggle
    │       │   └── EmailService.java
    │       │
    │       └── controller/                     ← HTTP layer only, delegates to services
    │           ├── AuthController.java
    │           ├── AppraisalController.java
    │           ├── DashboardController.java
    │           ├── RemarksController.java
    │           ├── AdminController.java
    │           ├── AnnouncementsController.java
    │           ├── FeedbackController.java
    │           ├── DocumentController.java
    │           └── UploadController.java
    │
    └── resources/
        ├── application.yml                     ← all config (DB, JWT, mail, storage, CORS)
        └── application-dev.yml                 ← local overrides (local storage, mock data)
```

---

## 6. File-by-file migration map

This maps every source file in the current FastAPI project to its Spring Boot equivalent.

### Setup / Infrastructure

| FastAPI file | Spring Boot equivalent | Notes |
|---|---|---|
| `src/main.py` | `AppraisalApplication.java` + `SecurityConfig.java` | CORS, middleware, exception handlers, static file serving all move to config classes |
| `src/setup/database.py` | `application.yml` (`spring.datasource.*`) | Async engine config → Spring DataSource bean. Pool size: `spring.datasource.hikari.maximum-pool-size=15` |
| `src/setup/dependencies.py` | `JwtAuthFilter.java` + `UserPrincipal.java` + `RoleHierarchy.java` | `get_current_user()` → JwtAuthFilter populates SecurityContext. `has_authority_over()` → method in RoleHierarchy. `get_form_family()` → static util method. |
| `src/setup/local_auth.py` | `JwtTokenProvider.java` | `create_access_token()` → `generateToken()`. `decode_access_token()` → `validateTokenAndGetEmail()`. BCryptPasswordEncoder is a Spring bean. |
| `src/setup/errors.py` | `AppException.java` + `ErrorResponse.java` | `AppError(user_message, detail)` → `AppException` extends `RuntimeException`. |
| `src/setup/storage_utils.py` | `StorageService.java` | Toggle via `app.storage.use-local=true/false` in yml. Same local path logic, GCS via Java SDK. |
| `src/setup/email_utils.py` | `EmailService.java` | SMTP config moves to `application.yml` (`spring.mail.*`). `send_verification_email()` → `sendVerificationEmail()` using Thymeleaf template or inline HTML. |
| `src/setup/admin_views.py` | **Not needed** | SQLAdmin panel is replaced entirely by the React `admin_ui/`. |
| `src/setup/supabase_client.py` | **Delete, do not port** | Dead code — not used in production. |

### Models → Entities

| FastAPI file | Spring Boot equivalent |
|---|---|
| `src/models/core.py` | `entity/core/*.java` (9 entity classes) |
| `src/models/part_a.py` | `entity/parta/*.java` (11 entity classes + 1 `@MappedSuperclass`) |
| `src/models/part_b.py` | `entity/partb/*.java` (14 entity classes + 1 `@MappedSuperclass`) |
| `src/models/non_teaching.py` | `entity/nonteaching/*.java` |

### Schemas → DTOs

| FastAPI file | Spring Boot equivalent |
|---|---|
| `src/schema/core.py` | `dto/auth/*.java`, `dto/admin/*.java`, `dto/appraisal/*.java` |
| `src/schema/part_a.py` | `dto/parta/*.java` (if needed for review endpoints) |
| `src/schema/part_b.py` | `dto/partb/*.java` |
| `src/schema/non_teaching.py` | `dto/nonteaching/*.java` |

### CRUD → Repositories + Services

| FastAPI file | Spring Boot equivalent |
|---|---|
| `src/crud/core.py` | `repository/core/*.java` + `UserService.java` |
| `src/crud/part_a.py` | `repository/parta/*.java` |
| `src/crud/part_b.py` | `repository/partb/*.java` |
| `src/crud/non_teaching.py` | `repository/nonteaching/*.java` + `NonTeachingService.java` |

### API Routes → Controllers + Services

| FastAPI file | Spring Boot equivalent |
|---|---|
| `src/api/v1/auth.py` | `AuthController.java` + `AuthService.java` |
| `src/api/v1/appraisal.py` | `AppraisalController.java` + `AppraisalService.java` |
| `src/api/v1/admin.py` | `AdminController.java` + `AdminService.java` |
| `src/api/v1/dashboard.py` | `DashboardController.java` + `DashboardService.java` |
| `src/api/v1/remarks.py` | `RemarksController.java` + `RemarksService.java` |
| `src/api/v1/non_teaching.py` | `NonTeachingController.java` + `NonTeachingService.java` |
| `src/api/v1/upload.py` | `UploadController.java` + `StorageService.java` |
| `src/api/v1/documents.py` | `DocumentController.java` |
| `src/api/v1/feedback.py` | `FeedbackController.java` + `FeedbackService.java` |
| `src/api/v1/announcements.py` | `AnnouncementsController.java` + `AnnouncementService.java` |

---

## 7. Key implementation patterns

### 7.1 JWT filter chain

In FastAPI, `get_current_user()` is a `Depends()` that runs per-request. In Spring Security, this becomes a filter:

```java
// JwtAuthFilter.java
@Component
public class JwtAuthFilter extends OncePerRequestFilter {

    @Override
    protected void doFilterInternal(HttpServletRequest req, HttpServletResponse res, FilterChain chain)
            throws ServletException, IOException {

        String header = req.getHeader("Authorization");
        if (header != null && header.startsWith("Bearer ")) {
            String token = header.substring(7);
            if (jwtTokenProvider.isValid(token)) {
                UserPrincipal principal = jwtTokenProvider.getPrincipal(token);
                UsernamePasswordAuthenticationToken auth =
                    new UsernamePasswordAuthenticationToken(principal, null, principal.getAuthorities());
                SecurityContextHolder.getContext().setAuthentication(auth);
            }
        }
        chain.doFilter(req, res);
    }
}
```

To get the current user in a controller, inject it via `@AuthenticationPrincipal`:

```java
@GetMapping("/me")
public ResponseEntity<?> getProfile(@AuthenticationPrincipal UserPrincipal user) {
    return ResponseEntity.ok(userService.getProfile(user.getEmail()));
}
```

### 7.2 Role hierarchy (has_authority_over)

The Python `has_authority_over()` method checks school/department/division. Port it as a Spring `@Service`:

```java
@Service
public class RoleHierarchy {

    private static final List<String> ENGINEERING = List.of("SoCSEA", "SoBB", "SoCE", "SoEMR");
    private static final List<String> NON_ENGINEERING = List.of("SoC", "SoMCS", "CioD", "SoAA");

    public boolean hasAuthorityOver(UserPrincipal reviewer, FacultyProfile target) {
        return switch (reviewer.getRole()) {
            case "admin", "vc" -> true;
            case "registrar" -> true; // non-teaching only — check separately
            case "dean" -> {
                boolean reviewerEng = ENGINEERING.contains(reviewer.getSchool());
                boolean targetEng = ENGINEERING.contains(target.getSchool());
                yield reviewerEng == targetEng; // same division
            }
            case "director", "center_head" ->
                reviewer.getSchool().equals(target.getSchool());
            case "hod" ->
                reviewer.getSchool().equals(target.getSchool()) &&
                reviewer.getDepartment().equals(target.getDepartment());
            default -> false;
        };
    }
}
```

### 7.3 shredForm — most complex service method

This is the centerpiece of `AppraisalService.java`. The Python version in `src/api/v1/appraisal.py` does:
1. Deletes existing rows for the user/year per section
2. Maps 20+ frontend JSON keys to ORM model classes
3. Handles field aliases (frontend name → DB column name)
4. Coerces types (string → int/float/date)
5. Inserts new rows

In Java, each section mapping becomes a handler method. Use a `Map<String, SectionHandler>` to keep it clean:

```java
@FunctionalInterface
interface SectionHandler {
    void handle(EntityManager em, String email, String year, String formFamily,
                List<Map<String, Object>> rows);
}

// In AppraisalService:
private final Map<String, SectionHandler> sectionHandlers = Map.of(
    "lectures",   (em, e, y, f, rows) -> shredSection(em, e, y, f, rows, TeachingProcess.class),
    "journals",   (em, e, y, f, rows) -> shredSection(em, e, y, f, rows, JournalPublication.class),
    // ... all 20+ sections
);
```

The field aliases map (frontend key → DB column) must be reproduced exactly:

```java
private static final Map<String, String> FIELD_ALIASES = Map.of(
    "title_with_page_nos", "title",
    "journal_details",     "journal",
    "issn_isbn_no",        "issn",
    "course_code_name",    "courseCode",
    "maxMarks",            "maxMarks",
    // ... all aliases from src/api/v1/appraisal.py field_aliases dict
);
```

Type coercion (Python `_coerce_for_column`) → Java `coerceValue(Field field, Object value)` using reflection on the entity class.

**Critical:** Test `shredForm` against real historical snapshot payloads from the DB before cutover. This is where most bugs will hide.

### 7.4 JSONB column (AppraisalSnapshot)

PostgreSQL JSONB columns need a custom JPA converter. The snapshot `payload` field stores the entire form as a JSON blob.

```java
// JsonbConverter.java
@Converter
public class JsonbConverter implements AttributeConverter<Map<String, Object>, String> {
    private final ObjectMapper mapper = new ObjectMapper();

    @Override
    public String convertToDatabaseColumn(Map<String, Object> attribute) {
        try { return mapper.writeValueAsString(attribute); }
        catch (JsonProcessingException e) { throw new RuntimeException(e); }
    }

    @Override
    public Map<String, Object> convertToEntityAttribute(String dbData) {
        try { return mapper.readValue(dbData, new TypeReference<>() {}); }
        catch (JsonProcessingException e) { throw new RuntimeException(e); }
    }
}

// In AppraisalSnapshot entity:
@Convert(converter = JsonbConverter.class)
@Column(columnDefinition = "jsonb")
private Map<String, Object> payload;
```

Also add to `application.yml`:
```yaml
spring.jpa.properties.hibernate.dialect: org.hibernate.dialect.PostgreSQLDialect
```

### 7.5 Error response format

Every error from the backend must return `{ "user_message": "...", "detail": "..." }`. This is consumed by both frontends — do not change this shape.

```java
// ErrorResponse.java
public record ErrorResponse(String userMessage, String detail) {}

// GlobalExceptionHandler.java
@RestControllerAdvice
public class GlobalExceptionHandler {

    @ExceptionHandler(AppException.class)
    public ResponseEntity<ErrorResponse> handleAppException(AppException ex) {
        return ResponseEntity
            .status(ex.getStatusCode())
            .body(new ErrorResponse(ex.getUserMessage(), ex.getDetail()));
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ErrorResponse> handleValidation(MethodArgumentNotValidException ex) {
        return ResponseEntity.status(422)
            .body(new ErrorResponse("Invalid request data. Please check your input.", ex.getMessage()));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<ErrorResponse> handleGeneric(Exception ex) {
        log.error("Unhandled exception", ex);
        return ResponseEntity.status(500)
            .body(new ErrorResponse("An unexpected error occurred. Please try again.", ex.getMessage()));
    }
}
```

Note: the JSON field must serialize as `user_message` (snake_case), not `userMessage`. Add to `application.yml`:
```yaml
spring.jackson.property-naming-strategy: SNAKE_CASE
```

### 7.6 CORS configuration

Current allowed origins are in `src/main.py`. Replicate in `SecurityConfig.java`:

```java
@Bean
public CorsConfigurationSource corsConfigurationSource() {
    CorsConfiguration config = new CorsConfiguration();
    config.setAllowedOrigins(List.of(
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:8000",
        "https://dypfacultyappraisal.netlify.app"
    ));
    config.setAllowedMethods(List.of("GET", "POST", "PUT", "DELETE", "OPTIONS"));
    config.setAllowedHeaders(List.of("*"));
    config.setAllowCredentials(true);

    UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
    source.registerCorsConfiguration("/api/**", config);
    return source;
}
```

### 7.7 Serving the React admin SPA

In FastAPI, the React `admin_ui` build is served at `/panel/`. Spring Boot equivalent:

```java
// In SecurityConfig or a WebMvcConfigurer:
@Override
public void addResourceHandlers(ResourceHandlerRegistry registry) {
    registry.addResourceHandler("/panel/**")
            .addResourceLocations("classpath:/static/panel/");
}

// SPA fallback — serve index.html for all /panel/* paths
@Controller
public class SpaController {
    @GetMapping("/panel/{path:^(?!api).*}")
    public String spa() {
        return "forward:/panel/index.html";
    }
}
```

Copy the `admin_ui` Vite build output into `src/main/resources/static/panel/` during the Docker build.

### 7.8 Submission cycle gate

Replicate the cycle gate from `src/api/v1/appraisal.py` in `AppraisalService.java`:

```java
public void checkCycleOpen(String academicYear) {
    appraisalConfigRepository.findByAcademicYear(academicYear).ifPresent(config -> {
        if (!config.isOpen()) {
            throw new AppException(
                "Appraisal submissions for " + academicYear + " are currently closed.",
                "Cycle gate: is_open=false for year " + academicYear,
                403
            );
        }
    });
    // No config row → allow (backwards compatible)
}
```

---

## 8. Environment variables

Map these from the Python `.env` to `application.yml`. All the same variable names apply — only the loading mechanism changes.

```yaml
# application.yml

spring:
  datasource:
    url: ${DATABASE_URL}            # jdbc:postgresql://... (not postgresql+asyncpg://)
    username: ${DB_USER:fac_user}
    password: ${DB_PASSWORD}
    hikari:
      maximum-pool-size: 15         # matches current pool_size=5 + max_overflow=10

  jpa:
    hibernate:
      ddl-auto: validate            # NEVER use create or update in production
    properties:
      hibernate.dialect: org.hibernate.dialect.PostgreSQLDialect

  mail:
    host: ${SMTP_HOST}
    port: ${SMTP_PORT:587}
    username: ${SMTP_USER}
    password: ${SMTP_PASSWORD}
    properties.mail.smtp.starttls.enable: true

app:
  jwt:
    secret: ${JWT_SECRET_KEY}
    expiry-days: 7
  url: ${APP_URL}
  frontend-url: ${FRONTEND_URL}
  storage:
    use-local: ${USE_LOCAL_STORAGE:false}
    gcs-bucket: ${GCP_STORAGE_BUCKET:}
  allow-mock-user: ${ALLOW_MOCK_USER:false}
```

**Note on DATABASE_URL:** The current Python value uses `postgresql+asyncpg://` scheme. For JDBC you need `jdbc:postgresql://`. When using Cloud SQL on Cloud Run, use the socket factory connector — see §10.

---

## 9. Database and migrations

No changes to the database. The same PostgreSQL instance continues to run.

**Connection on Cloud Run (Cloud SQL socket):**
```yaml
spring.datasource.url: jdbc:postgresql:///faculty_appraisal?cloudSqlInstance=facultyappraisal-495011:asia-south1:faculty-appraisal-db&socketFactory=com.google.cloud.sql.postgres.SocketFactory
```

**Connection locally (direct TCP):**
```yaml
# application-dev.yml
spring.datasource.url: jdbc:postgresql://localhost:5432/faculty_appraisal
```

**Schema management:** Keep using manual SQL migration files in `migrations/`. Do not enable Hibernate `ddl-auto: create` or `update` — it will corrupt your carefully-crafted schema. Use `ddl-auto: validate` (fails on startup if entities don't match tables) or `none`.

**If you want Flyway:** Flyway is the Spring-idiomatic migration tool. You can adopt it by:
1. Adding `spring-boot-starter-flyway` dependency
2. Renaming migration files to `V001__unique_constraints.sql`, `V002__...`, etc.
3. Placing them in `src/main/resources/db/migration/`
4. Flyway tracks which migrations have run in a `flyway_schema_history` table

This is optional but recommended for the long term.

---

## 10. Deployment changes

### Dockerfile

Replace the Python base image with a Java multi-stage build:

```dockerfile
# Stage 1: Build
FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /app
COPY pom.xml .
RUN mvn dependency:go-offline
COPY src ./src
# Copy admin_ui build into static resources
COPY admin_ui/dist ./src/main/resources/static/panel
RUN mvn package -DskipTests

# Stage 2: Run
FROM eclipse-temurin:21-jre-alpine
WORKDIR /app
COPY --from=build /app/target/*.jar app.jar
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
```

Spring Boot default port is 8080. Cloud Run expects 8080 by default, so no change needed there.

### Cloud Run

The current Cloud Build trigger pushes to Cloud Run. The Dockerfile change is the only required update. The `--add-cloudsql-instances` flag and all other `gcloud run deploy` flags stay the same.

### Admin panel build

The React `admin_ui/` build needs to be included in the Docker build. Two options:
1. **Bundle in Docker image** (recommended): Run `npm run build` in the Dockerfile before the Maven build and copy `admin_ui/dist` into `src/main/resources/static/panel/`.
2. **Deploy separately**: Deploy `admin_ui` to Netlify (like the main frontend) and point it at the Spring Boot backend. Simpler but removes the "same origin, no CORS" benefit.

---

## 11. Migration phases

### Phase 1 — Foundation (days 1–5)
- [ ] Create Spring Boot project with Maven
- [ ] Set up `SecurityConfig`, `JwtTokenProvider`, `JwtAuthFilter`, `UserPrincipal`
- [ ] Implement `RoleHierarchy` (port `has_authority_over()`)
- [ ] Configure `application.yml` and `application-dev.yml`
- [ ] Wire up PostgreSQL connection (local + Cloud SQL)
- [ ] Set up `GlobalExceptionHandler` with the `{user_message, detail}` shape
- [ ] Smoke test: `POST /api/v1/auth/login` returns a token

### Phase 2 — Auth routes (days 3–6, overlaps Phase 1)
- [ ] `AuthController` + `AuthService`: login, register, verify-email, me, change-password
- [ ] `EmailService`: verification email via JavaMailSender
- [ ] `StorageService` stub (local only for now)

### Phase 3 — Core API routes (days 6–16)
Port one controller+service pair per day. Suggested order (simplest → most complex):

1. `AnnouncementsController` — simple CRUD, no auth for GET
2. `FeedbackController` — simple CRUD
3. `AdminController` (users, config) — straightforward CRUD
4. `DocumentController` + `UploadController` — file handling, needs `StorageService`
5. `DashboardController` — complex joins, needs role checks
6. `RemarksController` — multi-step: write review + update section scores + advance status
7. `NonTeachingController` — separate form type, simpler than teaching
8. `AppraisalController` — last, because `shredForm` is the hardest

### Phase 4 — shredForm (days 14–20)
- [ ] Port `shredForm` to `AppraisalService.shredForm()`
- [ ] Port all 20+ section mappings with correct entity classes
- [ ] Port all field aliases from `field_aliases` dict
- [ ] Port `_coerce_for_column` type coercion logic
- [ ] Port `_extract_numeric_score` and `update_item_scores` from `remarks.py`
- [ ] Test against real snapshot payloads exported from production DB

### Phase 5 — Integration & parallel run (days 18–25)
- [ ] Deploy Spring Boot to a separate Cloud Run service (e.g., `faculty-appraisal-sb`)
- [ ] Point a staging frontend at the Spring Boot service
- [ ] Run all endpoints from `Docs/frontend_api_reference.md` against both backends
- [ ] Compare responses field-by-field for any discrepancy
- [ ] Fix any differences before cutover

### Phase 6 — Cutover
- [ ] Update Cloud Run service name / DNS / frontend env vars
- [ ] Monitor error rates for 24–48 hours
- [ ] Keep FastAPI service running (scaled to 0 instances) for one week as a rollback option
- [ ] Decommission FastAPI service after stable period

---

## 12. Testing strategy

### Unit tests
- `JwtTokenProvider`: generate token → decode → verify fields
- `RoleHierarchy`: test all role/school combinations for `hasAuthorityOver()`
- `AppraisalService.shredForm()`: feed a sample snapshot payload, verify correct rows are inserted per section
- `GlobalExceptionHandler`: verify `AppException` and validation errors produce correct JSON shape

### Integration tests (Spring Boot Test + TestContainers)
Use `@SpringBootTest` + a real PostgreSQL container (TestContainers) for:
- Full login → use token → call protected endpoint flow
- Submit appraisal → verify declarations and section rows in DB
- Review flow: faculty submits → HOD reviews → Director reviews → status progression

### Contract tests
The most important test: for every endpoint in `Docs/frontend_api_reference.md`, write a test that sends the documented request and asserts the documented response shape. These tests are the migration acceptance criteria.

---

## 13. Risks and gotchas

| Risk | Mitigation |
|---|---|
| `shredForm` has subtle field coercion behavior (e.g., empty string → null, `"5.0"` → integer `5`) | Export real snapshots from prod DB. Test against them, not synthetic data. |
| JSONB column behavior differences between SQLAlchemy and Hibernate | Use the `JsonbConverter` pattern in §7.4. Test round-trips carefully. |
| JWT tokens issued by FastAPI must remain valid through cutover | Use the same `JWT_SECRET_KEY` and HS256 algorithm. Verify with jjwt's `Jwts.parser()`. |
| `statement_cache_size: 0` was set for Supabase/PgBouncer compatibility — not needed for Cloud SQL | HikariCP (Spring Boot's default pool) + Cloud SQL socket factory do not use PgBouncer. No special setting needed. |
| Async vs blocking | FastAPI used `async def` throughout. Spring MVC is blocking (thread-per-request). For this scale (single university), this is fine. Do not use Spring WebFlux/R2DBC — it adds complexity without benefit here. |
| `supabase_client.py` dead code | Do not port it. If any code path still touches Supabase, remove it in FastAPI first before migrating. |
| `forgot-password` and `reset-password` endpoints are stubs (not implemented) in FastAPI | Either implement them properly in Spring Boot or leave them as 501 stubs with a clear TODO comment. |
| Local file serving (`/uploads/*`) | In FastAPI this is a Starlette `StaticFiles` mount. In Spring Boot, use `ResourceHandlerRegistry` as shown in §7.7. Ensure the upload path is the same (`./uploads/`). |
| `pool_size=5, max_overflow=10` | Translate to `hikari.maximum-pool-size=15`. Cloud SQL max connections ~100; keep Cloud Run `max-instances` in mind. |
| Docker image runs as root | Still acceptable for Cloud Run (managed environment), but worth fixing for on-premise. Add `RUN adduser --system appuser && USER appuser` before `ENTRYPOINT` in the Dockerfile. |
