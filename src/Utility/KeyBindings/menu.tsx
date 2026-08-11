/**
 * UI components for rendering the key binding help menu and action buttons.
 * Provides modal, dropdown, and context menu variants for registered bindings.
 * @packageDocumentation
 */

import { useEffect, useRef, useState } from "react";
import type { MouseEvent } from "react";
import { Accordion, Button, ButtonGroup, Dropdown } from "react-bootstrap";
import { InfoPopUp } from "../UI";
import { AlertModal } from "../UI";
import { useAction, useKeyBindingContext } from "./context";
import { useKeyPress } from "./useKeyPress";
import { KeyBindingInfo, KeyPressArgs } from "./types";
import { getCategories, getKeyDescription, groupBy } from "./utils";

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
    if(show) {
      setkeyB(new Array<KeyBindingInfo>().concat(x.keyBindings));
    }
  }, [show, x.keyBindings]);

  return (
    <AlertModal
      title="Help"
      message={
        <div style={{ maxHeight: "75vh", overflowY: "auto" }}>
          {getCategories(keyB).map((category: string): JSX.Element => (
            <div key={category}>
              <Accordion defaultActiveKey={category}>
                <Accordion.Item eventKey={category}>
                  <Accordion.Header>{category}</Accordion.Header>
                  <Accordion.Body>
                    <KeyBindingMenuForCategory keyB={keyB} category={category} />
                  </Accordion.Body>
                </Accordion.Item>
              </Accordion>
              <p></p>
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
  if(!actions) {
    return <p>No Actions for category {category} found!</p>;
  }
  return actions.map((binding: KeyBindingInfo, index: number): JSX.Element => (
    <div key={`${binding.eventDescription}-${index}`}>
      <p>
        <a
          href=""
          onClick={(e: MouseEvent<HTMLAnchorElement>): void => {
            e.preventDefault();
            binding.action();
          }}
        >
          {binding.icon ? binding.icon : <></>} {binding.description}
        </a>{" "}
        (Press <b>{getKeyDescription(binding.eventDescription)}</b>)
      </p>
      <p></p>
    </div>
  ));
}

/** Render all actions for a category using the current context. */
export function ActionMenuForCategory({ category }: { category: string }): JSX.Element {
  const x = useKeyBindingContext();
  return <KeyBindingMenuForCategory category={category} keyB={x.keyBindings} />;
}

/** Render actions as dropdown items grouped by category. */
export function KeyBindingsAsDropdownItems(): JSX.Element {
  const x = useKeyBindingContext();
  return (
    <>
      {getCategories(x.keyBindings).map((cat: string): JSX.Element => (
        <div key={cat}>
          <Dropdown.Header>{cat}</Dropdown.Header>
          {groupBy(x.keyBindings, "category")[cat].map(
            (kb: KeyBindingInfo, index: number): JSX.Element => (
              <Dropdown.Item
                key={`${kb.eventDescription}-${index}`}
                onClick={(): void => kb.action()}
              >
                {kb.icon ? kb.icon : <></>} {kb.description} [
                {getKeyDescription(kb.eventDescription)}]
              </Dropdown.Item>
            ),
          )}
        </div>
      ))}
    </>
  );
}

/** Render a row of action buttons for a category. */
export function ContextMenu({ category }: { category: string }): JSX.Element {
  const actionsContext = useKeyBindingContext();
  const menuRef = useRef<HTMLDivElement>(null);
  return (
    <ButtonGroup className="vci-context-menu-group" style={{ marginRight: "4px" }} ref={menuRef}>
      {(groupBy(actionsContext.keyBindings, "category")[category] || []).map(
        (kb: KeyBindingInfo, index: number): JSX.Element => (
          <KeyBindingButton
            key={`${kb.eventDescription}-${index}`}
            kb={kb}
            menu={menuRef.current?.parentElement || undefined}
          />
        ),
      )}
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
    <>
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
          onClick={(): void => {
            kb.action();
          }}
          style={{
            backgroundColor: "var(--bs-dark)",
          }}
        >
          {kb.icon ? kb.icon : kb.description}
        </Button>
      </InfoPopUp>
    </>
  );
}

/** Button that registers a key press and exposes it as a UI action. */
export function ButtonWithKeyPress({ args }: { args: KeyPressArgs }): JSX.Element {
  useKeyPress({ category: "Default", ...args });
  const action = useAction(args.key);
  if(!action) return <p>Action {args.description} currently not available</p>;
  return <KeyBindingButton kb={action} />;
}

/** Button that looks up an existing action by key binding name. */
export function ButtonWithKey({ keybinding }: { keybinding: string }): JSX.Element {
  const action = useAction(keybinding);
  if(!action) return <p>Action {keybinding} currently not available</p>;
  return <KeyBindingButton kb={action} />;
}
