import { useRef } from "react";
import { Badge, OverlayTrigger, Popover } from "react-bootstrap";
import { Placement } from "react-bootstrap/esm/types";

export function InfoPopUpBadge({
    title,
    longTitle,
    content,
    placement,
    onClick = () => { },
    bg = "info",
    icon = "ⓘ",
    useBody = false
}: InfoPopUpBadgeProps) {
    const badgeRef = useRef<HTMLSpanElement>(null);
    return (
        <InfoPopUp
            title={title}
            longTitle={longTitle}
            content={content}
            placement={placement}
            parentElement={useBody ? undefined : badgeRef.current?.parentElement?.parentElement || undefined}
        >
            <Badge
                pill
                bg={bg}
                onClick={() => {
                    onClick();
                }}
                ref={badgeRef}
            >
                {icon} {title}
            </Badge>
        </InfoPopUp>
    );
}

type PopUpProps = {
    title?: any;
    longTitle?: any;
    content: any;
    placement?: Placement;
}

type InfoPopUpBadgeProps = PopUpProps & {
    bg?: string;
    icon?: any;
    onClick?: () => void;
    useBody?: boolean;
}

type InfoPopUpProps = PopUpProps & {
    children: any;
    parentElement?: HTMLElement;
}

export function InfoPopUp({
    title = "",
    longTitle = null,
    content,
    children,
    placement = "right",
    parentElement = document.body,
}: InfoPopUpProps) {
    return (
        <OverlayTrigger
            trigger={["hover", "focus"]}
            key={placement}
            placement={placement}
            container={parentElement ? parentElement : undefined}
            overlay={
                <Popover id={`popover-positioned-${placement}`}>
                    {longTitle && <Popover.Header as="h3">{longTitle}</Popover.Header>}
                    <Popover.Body>{content}</Popover.Body>
                </Popover>
            }
        >
            {children}
        </OverlayTrigger>
    );
}
