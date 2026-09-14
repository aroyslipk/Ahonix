import React, { createContext, useContext, useState } from "react";

const UIContext = createContext(null);

export function UIProvider({ children }) {
  const [askOpen, setAskOpen] = useState(false);
  const [askSeed, setAskSeed] = useState(null); // pre-filled question

  const openAsk = (seed = null) => {
    setAskSeed(seed);
    setAskOpen(true);
  };

  return (
    <UIContext.Provider value={{ askOpen, setAskOpen, askSeed, setAskSeed, openAsk }}>
      {children}
    </UIContext.Provider>
  );
}

export const useUI = () => useContext(UIContext);
