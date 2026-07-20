import {
    ZoomIn,
    ZoomOut,
    Maximize2Icon,
    Star,
    Menu,
    ArrowUp,
    ArrowDown,
    ArrowLeft,
    ArrowRight,
    ChevronDown,
    ChevronRight,
    ChevronLeft,
    RefreshCw,
    Layers,
    Expand,
    Sunrise,
    Sunset,
    Gauge,
    Info,
    Cable
} from "lucide-react";

export const exposureIconPlus = <Sunrise />
export const exposureIconMinus = <Sunset />

export const downloadIcon = <Layers />;
export const fullscreenIcon = <Expand />;
export const nextItem = <ChevronRight />;
export const previousItem = <ChevronLeft />;
export const menuIcon = <Menu />;

// An empty (outline) star
export const emptyStar = <Star stroke="#ebd021" />;
// A filled star—give it both fill and stroke so it's solid
export const filledStar = <Star fill="#ebd021" stroke="#ebd021" />;

export const upIcon = <ArrowUp />;
export const downIcon = <ArrowDown />;
export const leftIcon = <ArrowLeft />;
export const rightIcon = <ArrowRight />;

export const zoomInIcon = <ZoomIn />;
export const zoomOutIcon = <ZoomOut />;
export const resetZoomCenterIcon = <RefreshCw />;
export const setZoom1_1Icon = <span>1:1</span>;
export const resetZoomIconFull = <Maximize2Icon />;
export const expandIcon = <ChevronDown />;

export const performanceIcon = <Gauge />;

export const infoIcon = <Info />;

export const triggerSource = <Cable />