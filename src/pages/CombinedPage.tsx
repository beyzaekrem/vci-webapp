import React, { useEffect } from "react";
import { Navbar } from "react-bootstrap";
import Nav from "react-bootstrap/Nav";
import { NavLink, useLocation, useNavigate, useParams } from "react-router-dom";
import { StreamsPerServer } from "../Components/Videostream";

import { expandIcon } from "../Components/Icons.tsx";

const url = "/preview";

interface TabProps {
  tabKey: string;
  title: string;
  renderTitle?: React.ReactNode;
  children: (tabKey: string) => React.ReactNode;
}

export function CombinedPage() {
  const tabKey = useParams().tabKey;
  const navigate = useNavigateToTab();

  // We need to define the tabs here because we need to check if the tabKey is valid later

  const tabData = [
    {
      tabKey: "streams_per_server",
      title: "Preview Streams",
      children: (tabKey) => (
        <>
          {
            /* only render if tab is active to keep help menu small */
            tabKey === "streams_per_server" && (
              <div style={{ height: " calc(100vh - (95px))" }}>
                <StreamsPerServer />
              </div>
            )
          }
        </>
      ),
    },

  ] as TabProps[];

  useEffect(() => {
    if(!tabKey || !tabData.find((tab) => tab.tabKey === tabKey)) {
      const dat = tabData.at(0)
      if(dat) {
        navigate(dat.tabKey);
      }
    }
  }, [tabKey]);

  return (
    <>
      <Navbar /*expand="lg"*/ className="p-0">
        <Navbar.Toggle
          aria-controls="responsive-navbar-nav"
          className="position-fixed"
          style={{ top: 10, right: 10 }}
        >
          {expandIcon}
        </Navbar.Toggle>
        <Navbar.Collapse id="responsive-navbar-nav">
          <Nav className="w-100">
            {tabData.map(({ tabKey, title, renderTitle }) => (
              <Nav.Item key={tabKey} className="flex-fill text-center">
                <Nav.Link
                  as={NavLink}
                  to={`${url}/${tabKey}`}
                  onClick={(e) => {
                    e.preventDefault();
                    navigate(tabKey);
                  }}
                  eventKey={tabKey}
                >
                  {window.innerWidth > 992 ? renderTitle || title : title}
                </Nav.Link>
              </Nav.Item>
            ))}
          </Nav>
        </Navbar.Collapse>
      </Navbar>
      {tabKey && tabData.find((tab) => tab.tabKey === tabKey)?.children(tabKey)}
    </>
  );
}

function useNavigateWithQueryParams() {
  const navigate = useNavigate();
  const location = useLocation();
  return (path: string) => {
    navigate({
      pathname: path,
      search: location.search,
    });
  };
}

function useNavigateToTab() {
  const navigate = useNavigateWithQueryParams();
  const params = useParams();
  return (tabKey: string) => navigate(`${url}/${tabKey}`);
}
