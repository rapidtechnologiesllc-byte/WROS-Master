import { useState } from "react";
import Login from "../components/Login";
import Signup from "../components/Signup";

export default function AuthPage() {
  const [isLogin, setIsLogin] = useState(true);

  return (
    <div className="w-full max-w-md bg-white shadow-lg rounded-2xl p-8">
      {isLogin ? (
        <Login onSwitch={() => setIsLogin(false)} />
      ) : (
        <Signup onSwitch={() => setIsLogin(true)} />
      )}
    </div>
  );
}
