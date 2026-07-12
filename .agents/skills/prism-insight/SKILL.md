```markdown
# prism-insight Development Patterns

> Auto-generated skill from repository analysis

## Overview
This skill teaches you the core development patterns and conventions used in the `prism-insight` TypeScript codebase. It covers file organization, code style, commit practices, and how to write and run tests. By following these guidelines, you'll ensure consistency and maintainability across the project.

## Coding Conventions

### File Naming
- Use **kebab-case** for all file and folder names.
  - Example:  
    ```
    user-profile.ts
    data-utils/
    ```

### Import Style
- Use **relative imports** for modules within the project.
  - Example:
    ```typescript
    import { fetchData } from './data-utils';
    ```

### Export Style
- Use **named exports** for all exported functions, types, and constants.
  - Example:
    ```typescript
    // In data-utils.ts
    export function fetchData() { ... }
    export const DATA_LIMIT = 100;
    ```

### Commit Messages
- Follow the **Conventional Commits** specification.
- Use the `chore` prefix for maintenance and non-feature changes.
  - Example:
    ```
    chore: update dependencies to latest versions
    ```

## Workflows

### Code Changes and Commits
**Trigger:** When making any code or documentation change  
**Command:** `/commit`

1. Make your code changes following the coding conventions.
2. Stage your changes with `git add`.
3. Write a commit message using the conventional commit format, typically starting with `chore:`.
   - Example:  
     ```
     chore: refactor data fetching logic
     ```
4. Commit your changes.

### Writing Tests
**Trigger:** When adding new features or fixing bugs  
**Command:** `/write-test`

1. Create a test file with the `.test.ts` extension, following kebab-case.
   - Example:  
     ```
     data-utils.test.ts
     ```
2. Write your test cases using the project's testing framework (unknown, but follow existing patterns).
3. Use named exports for test helpers if needed.

### Running Tests
**Trigger:** Before pushing changes or merging  
**Command:** `/run-tests`

1. Run the test suite using the project's test runner (refer to project documentation or scripts).
2. Ensure all tests in `*.test.ts` files pass.

## Testing Patterns

- Test files use the `*.test.ts` naming convention.
- Place test files alongside the modules they test or in a dedicated test directory.
- Follow the same import/export conventions as source files.
- Example test file structure:
  ```typescript
  // data-utils.test.ts
  import { fetchData } from './data-utils';

  describe('fetchData', () => {
    it('should return expected data', () => {
      // test implementation
    });
  });
  ```

## Commands
| Command       | Purpose                                      |
|---------------|----------------------------------------------|
| /commit       | Commit code changes with conventional format |
| /write-test   | Create and write tests for new code          |
| /run-tests    | Run the test suite                           |
```