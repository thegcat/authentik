import { AKElement } from "@goauthentik/elements/Base";
import "@goauthentik/elements/EmptyState";
import { type SlottedTemplateResult, type Spread } from "@goauthentik/elements/types";
import { spread } from "@open-wc/lit-helpers";

import { css, html, nothing } from "lit";
import { customElement, property } from "lit/decorators.js";

import PFBase from "@patternfly/patternfly/patternfly-base.css";

export interface ILoadingOverlay {
    topmost?: boolean;
}

/**
 * @class LoadingOverlay
 * @element ak-loading-overlay
 *
 * The LoadingOverlay is meant to cover the container element completely, hiding the content behind
 * a dimming filter, while content loads.
 *
 * @slot "body" - [Optional] message content to display while the overlay is visible.
 */
@customElement("ak-loading-overlay")
export class LoadingOverlay extends AKElement implements ILoadingOverlay {
    /**
     * When true, forces the overlay onto the top layer of the display stack.
     * Do not camelize: https://www.merriam-webster.com/dictionary/topmost
     *
     * @attr
     */
    @property({ type: Boolean, attribute: "topmost" })
    topmost = false;

    static get styles() {
        return [
            PFBase,
            css`
                :host {
                    display: flex;
                    height: 100%;
                    width: 100%;
                    justify-content: center;
                    align-items: center;
                    position: absolute;
                    background-color: var(--pf-global--BackgroundColor--dark-transparent-200);
                    z-index: 1;
                }
                :host([topmost]) {
                    z-index: 999;
                }
            `,
        ];
    }

    render() {
        return html`<ak-empty-state loading header="">
            <span slot="body"><slot></slot></span>
        </ak-empty-state>`;
    }
}

export function akLoadingOverlay(
    properties: ILoadingOverlay,
    content: SlottedTemplateResult = nothing,
) {
    const message = typeof content === "string" ? html`<span>${content}</span>` : content;
    return html`<ak-loading-overlay ${spread(properties as Spread)}
        >${message}</ak-loading-overlay
    >`;
}

declare global {
    interface HTMLElementTagNameMap {
        "ak-loading-overlay": LoadingOverlay;
    }
}
