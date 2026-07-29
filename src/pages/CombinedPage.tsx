import { useEffect } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { PreviewStreamsPage } from "../Components/PreviewStreams";

const url = "/preview";

export function CombinedPage() {
  const tabKey = useParams().tabKey;
  const navigate = useNavigateToTab();

  useEffect(() => {
    if (!tabKey || tabKey !== "streams_per_server") {
      navigate("streams_per_server");
    }
  }, [tabKey]);

  return <PreviewStreamsPage />;
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
  return (tabKey: string) => navigate(`${url}/${tabKey}`);
}
