// src/pages/AuthPage.jsx
import { useState } from "react";
import Login from "../components/Login";
import Signup from "../components/Signup";

export default function AuthPage({ onAuthSuccess }) {
  const [isLogin, setIsLogin] = useState(true);

  return isLogin ? (
    <Login
      onSwitch={() => setIsLogin(false)}
      onSuccess={(userObj) => onAuthSuccess(userObj)}
    />
  ) : (
    <Signup
      onSwitch={() => setIsLogin(true)}
      onSuccess={(userObj) => onAuthSuccess(userObj)}
    />
  );
}
