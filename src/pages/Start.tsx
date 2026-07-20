import { Container } from "react-bootstrap";
import { ServerOverview } from "../Components/ServerOverview.tsx";

export function StartPage() {
  return (
    <div
      className="d-flex justify-content-center"
    >
      <div>
        <Container style={{ maxWidth: "600px", margin: "20px auto" }}>
          <h1 style={{ margin: "15px" }}>Capture Servers</h1>
          <ServerOverview />
        </Container>
      </div>
    </div>
  );
}
