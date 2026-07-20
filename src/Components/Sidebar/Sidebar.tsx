import { useState } from "react";
import { Button, Nav, Offcanvas } from "react-bootstrap";
import { NavLink } from "react-router-dom";
import { ButtonWithKey } from "../../Utility/KeyBindings/index.ts";
import { menuIcon } from "../Icons.tsx";
import "./sidebar.css"

export function Sidebar() {
  const [show, setShow] = useState(false);

  const handleClose = () => setShow(false);
  const handleShow = () => setShow(true);

  return (
    <>
      <Button className="sidebar-button" variant="primary" onClick={handleShow}>
        {menuIcon}
      </Button>

      <Offcanvas show={show} onHide={handleClose}>
        <Offcanvas.Header closeButton>
          <Offcanvas.Title>VCI Web App</Offcanvas.Title>
        </Offcanvas.Header>
        <Offcanvas.Body>
          <Nav className="flex-column">
            <Nav.Item>
              <Nav.Link as={NavLink} to="/preview">
                Preview
              </Nav.Link>
            </Nav.Item>

            <Nav.Item>
              <Nav.Link as={NavLink} to="/vci-automation">
                VCI Automation
              </Nav.Link>
            </Nav.Item>

            <Nav.Item>
              <Nav.Link as={NavLink} to="/capture">
                Capture
              </Nav.Link>
            </Nav.Item>

            <Nav.Item>
              <Nav.Link as={NavLink} to="/calibrate">
                Calibrate
              </Nav.Link>
            </Nav.Item>

            <Nav.Item>
              <Nav.Link as={NavLink} to="/servers">
                Server Status
              </Nav.Link>
            </Nav.Item>

            <Nav.Item>
              <Nav.Link as={NavLink} to="/config">
                Settings
              </Nav.Link>
            </Nav.Item>
            <Nav.Item>
              <Nav.Link as={NavLink} to="/about">
                About
              </Nav.Link>
            </Nav.Item>

            <ButtonWithKey keybinding="h" />
          </Nav>
        </Offcanvas.Body>
      </Offcanvas>
    </>
  );
}
