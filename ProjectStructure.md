# Project Structure

The Project contains

- UI Elements for the webapp
- Network code for communicating with the servers, including
  - A generic InterceptorConnection class that can be used to implement new server connections to Interceptor endpoints
  - Classes that use InterceptorConnection to implement the communication with the ControlServer and CaptureServer
- Utility code, containing helper functions, custom hooks and generic UI components

The Project is split accordingly and follows some general rules:

- Utility code does not depend on anything else in the project, it is purely self-contained. It can be used in any other project without modification.
- Network code does not depend on anything else in the project (except for Utility/Storage)
- ...

Rules can be found in the dependency-cruiser configuration (`./dependency-cruiser.cjs`, `./dependency-cruiser.components.cjs`) and violations of these rules are visually represented in the dependency graphs below.

Run `npm run dependency_cruise` to generate a dependency graph of the whole project to check for violations of these rules, or rebuild the docs by rebuilding the application to update the images in the hosted documentation.

<img src="./deps.svg" alt="Project structure" max-width="1200px">

<p style="margin-top: 3px; margin-bottom: 20px; padding: 0 0; text-align: center; font-size: 12px;">
Project structure and dependencies for general overview.
</p>

<img src="./deps.components.svg" alt="Component dependencies" max-width="1200px">

<p style="margin-top: 3px; margin-bottom: 20px; padding: 0 0; text-align: center; font-size: 12px;">
Dependency graph of <code>src/Components</code>. Shows which components depend on which other components.
</p>
