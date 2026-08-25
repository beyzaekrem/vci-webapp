import { useEffect, useRef, useState } from "react";
import type { MouseEvent } from "react";
import { Accordion, Button, ButtonGroup, Dropdown } from "react-bootstrap";
import { InfoPopUp, AlertModal } from "../UI";
import { KeyBindingCategory, KeyBindingInfo, KeyPressArgs } from "./types";
import { useKeyPress } from "./useKeyPress";
import { getCategories, getKeyDescription, groupBy } from "./utils";
import { useAction, useKeyBindingContext } from "./context";

/** Help modal showing available key bindings grouped by category. */
export function KeyBindingMenu(): JSX.Element {
  const [show, setShow] = useState(false);

  useKeyPress({
    key: "h",
    onKeyEvent: (): void => setShow((show: boolean): boolean => !show),
    description: "Show Help Menu",
    category: "Help",
  });

  const x = useKeyBindingContext();

  const [keyB, setkeyB] = useState(new Array<KeyBindingInfo>());
  useEffect((): void => {
    if (show) {
      setkeyB(new Array<KeyBindingInfo>().concat(x.keyBindings));
    }
  }, [show, x.keyBindings]);

  return (
    <AlertModal
      title="Help / Keyboard Shortcuts"
      message={
        <div style={{ maxHeight: "75vh", overflowY: "auto" }}>
          {getCategories(keyB).map((category: string): JSX.Element => (
            <div key={category} style={{ marginBottom: "12px" }}>
              <Accordion defaultActiveKey={category}>
                <Accordion.Item eventKey={category}>
                  <Accordion.Header>{category}</Accordion.Header>
                  <Accordion.Body>
                    <KeyBindingMenuForCategory keyB={keyB} category={category} />
                  </Accordion.Body>
                </Accordion.Item>
              </Accordion>
            </div>
          ))}
        </div>
      }
      show={show}
      setShow={setShow}
      showCancel={false}
      modalProps={{ size: "lg" }}
    />
  );
}

/** Props for rendering a category section of key bindings. */
interface KeyBindingMenuForCategoryProps {
  keyB: KeyBindingInfo[];
  category: string;
}

/** Render all key bindings for a specific category section. */
function KeyBindingMenuForCategory({
  keyB,
  category,
}: KeyBindingMenuForCategoryProps) {
  const actions = groupBy(keyB, "category")[category];
  if (!actions) {
    return <p>No Actions for category {category} found!</p>;
  }
  return actions.map((binding: KeyBindingInfo, index: number): JSX.Element => (
    <div key={`${binding.eventDescription}-${index}`} style={{ marginBottom: "6px" }}>
      <p style={{ margin: 0 }}>
        <a
          href=""
          onClick={(e: MouseEvent<HTMLAnchorElement>): void => {
            e.preventDefault();
            binding.action();
          }}
          style={{ fontWeight: 600, color: "#0284c7" }}
        >
          {binding.icon ? binding.icon : <></>} {binding.description}
        </a>{" "}
        (Press <b>{getKeyDescription(binding.eventDescription)}</b>)
      </p>
    </div>
  ));
}

/** Render a drop-down menu of all registered actions in a category. */
export function ContextMenu({
  category,
}: {
  category: KeyBindingCategory;
}): JSX.Element {
  const actionsContext = useKeyBindingContext();
  const categoryActions = (groupBy(actionsContext.keyBindings, "category")[category] || []);
  const menuRef = useRef<HTMLDivElement>(null);

  if (categoryActions.length === 0) return <></>;

  return (
    <Dropdown className="d-inline" ref={menuRef}>
      <Dropdown.Toggle variant="light" size="sm" style={{ border: "1px solid #cbd5e1", fontSize: "12px", fontWeight: 600, color: "#334155", background: "#f8fafc" }}>
        {category} Controls
      </Dropdown.Toggle>

      <Dropdown.Menu className="shadow-sm" style={{ padding: "6px" }}>
        {categoryActions.map((kb: KeyBindingInfo, index: number) => (
          <Dropdown.Item
            key={`${kb.eventDescription}-${index}`}
            as="div"
            style={{ padding: "4px 8px" }}
          >
            <KeyBindingButton kb={kb} />
          </Dropdown.Item>
        ))}
      </Dropdown.Menu>
    </Dropdown>
  );
}

/** Render a group of buttons for all actions in a category. */
export function KeyBindingButtonGroup({
  category,
}: {
  category: KeyBindingCategory;
}): JSX.Element {
  const actionsContext = useKeyBindingContext();
  const categoryActions = (groupBy(actionsContext.keyBindings, "category")[category] || []);
  const menuRef = useRef<HTMLDivElement>(null);

  if (categoryActions.length === 0) return <></>;

  return (
    <ButtonGroup className="vci-context-menu-group" ref={menuRef}>
      {categoryActions.map((kb: KeyBindingInfo, index: number) => (
        <KeyBindingButton
          key={`${kb.eventDescription}-${index}`}
          kb={kb}
          menu={menuRef.current?.parentElement || undefined}
        />
      ))}
    </ButtonGroup>
  );
}

/** Render a single key binding as a button with tooltip info. */
export function KeyBindingButton({
  kb,
  menu,
}: {
  kb: KeyBindingInfo;
  menu?: HTMLElement | undefined;
}): JSX.Element {
  const keys = getKeyDescription(kb.eventDescription);
  return (
    <InfoPopUp
      content={
        <>
          {kb.description} [{keys}]
        </>
      }
      placement="bottom"
      parentElement={menu}
    >
      <Button
        type="button"
        className="vci-keybinding-btn"
        onClick={(): void => {
          kb.action();
        }}
      >
        {kb.icon ? kb.icon : kb.description}
      </Button>
    </InfoPopUp>
  );
}

/** Button that registers a key press and exposes it as a UI action. */
export function ButtonWithKeyPress({ args }: { args: KeyPressArgs }): JSX.Element {
  useKeyPress({ category: "Default", ...args });
  const keyName = Array.isArray(args.key) ? args.key[0] : args.key;
  const action = useAction(keyName);
  if (!action) return <p>Action {args.description} currently not available</p>;
  return <KeyBindingButton kb={action} />;
}

/** Button that looks up an existing action by key binding name. */
export function ButtonWithKey({ keybinding }: { keybinding: string }): JSX.Element {
  const action = useAction(keybinding);
  if (!action) return <p>Action {keybinding} currently not available</p>;
  return <KeyBindingButton kb={action} />;
}
